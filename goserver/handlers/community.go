package handlers

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"sort"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
	"scwiki/server/cache"
	"scwiki/server/middleware"
	"scwiki/server/models"
)

func RegisterCommunityRoutes(r *gin.Engine) {
	read := r.Group("/api/community", middleware.OptionalAuth)
	read.GET("/questions", communityQuestions)
	read.GET("/entries", communityEntries)
	read.GET("/entries/:id", communityGetEntry)
	read.GET("/systems/:key", communitySystem)
	write := r.Group("/api/community", middleware.AuthRequired, communityWriter)
	write.POST("/entries", communityCreate)
	write.PATCH("/entries/:id", communityEdit)
	write.DELETE("/entries/:id", communityDelete)
	write.PUT("/entries/:id/vote", communityVote)
	write.DELETE("/entries/:id/vote", communityVote)
	write.POST("/entries/:id/reports", communityReport)
	write.POST("/entries/:id/moderate", middleware.AdminRequired, communityModerate)
	write.GET("/moderation/reports", middleware.AdminRequired, communityReports)
	auth := r.Group("/api/community", middleware.AuthRequired)
	auth.GET("/notifications", communityNotifications)
	auth.GET("/notifications/unread", communityUnread)
	auth.PATCH("/notifications/read", communityReadNotifications)
}

type communityError struct {
	status int
	code   string
}

func (e communityError) Error() string { return e.code }
func communityFail(c *gin.Context, err error) {
	var problem communityError
	if errors.As(err, &problem) {
		c.JSON(problem.status, gin.H{"error": problem.code, "code": problem.code})
		return
	}
	if errors.Is(err, gorm.ErrRecordNotFound) {
		c.JSON(404, gin.H{"error": "content_unavailable", "code": "content_unavailable"})
		return
	}
	c.Error(err)
	c.JSON(500, gin.H{"error": "community_unavailable", "code": "community_unavailable"})
}
func communityBad() error { return communityError{400, "invalid_community_input"} }
func communityViewer(c *gin.Context) *models.User {
	value, ok := c.Get("current_user")
	if !ok {
		return nil
	}
	user, _ := value.(*models.User)
	return user
}
func communityWriter(c *gin.Context) {
	u := communityViewer(c)
	if u == nil || u.AccountStatus != "active" || !u.IsEmailVerified {
		c.Abort()
		communityFail(c, communityError{403, "verified_account_required"})
		return
	}
	c.Next()
}
func communityBind(c *gin.Context, dest any) error {
	c.Request.Body = http.MaxBytesReader(c.Writer, c.Request.Body, 128<<10)
	decoder := json.NewDecoder(c.Request.Body)
	decoder.DisallowUnknownFields()
	if decoder.Decode(dest) != nil {
		return communityBad()
	}
	if err := decoder.Decode(new(any)); err != io.EOF {
		return communityBad()
	}
	return nil
}
func communityPage(c *gin.Context) (int, int, error) {
	limit, e1 := strconv.Atoi(c.DefaultQuery("limit", "20"))
	offset, e2 := strconv.Atoi(c.DefaultQuery("offset", "0"))
	if e1 != nil || e2 != nil || limit < 1 || limit > 50 || offset < 0 || offset > 100000 {
		return 0, 0, communityBad()
	}
	return limit, offset, nil
}
func communityID(raw string) (uint, error) {
	n, e := strconv.ParseUint(raw, 10, 32)
	if e != nil || n == 0 {
		return 0, communityBad()
	}
	return uint(n), nil
}
func communityLength(s string, min, max int) bool {
	n := utf8.RuneCountInString(s)
	return utf8.ValidString(s) && n >= min && n <= max
}

// 限流故障拒绝写入，避免服务重启或多实例绕过限额。
func communityLimit(c *gin.Context, category string) error {
	u := communityViewer(c)
	if u == nil {
		return communityError{401, "authentication_required"}
	}
	max, window := int64(30), time.Minute
	switch category {
	case "question":
		max, window = 10, time.Hour
	case "action":
		max = 60
	}
	for _, quota := range []struct {
		key string
		max int64
		ttl time.Duration
	}{
		{fmt.Sprintf("community:user:%d:%s", u.ID, category), max, window},
		{"community:ip:" + c.ClientIP(), 120, time.Minute},
	} {
		n, err := cache.IncrementWindow(quota.key, quota.ttl)
		if err != nil {
			return communityError{503, "community_rate_limit_unavailable"}
		}
		if n > quota.max {
			c.Header("Retry-After", strconv.Itoa(int(quota.ttl.Seconds())))
			return communityError{429, "community_rate_limited"}
		}
	}
	return nil
}

// 从已有元素目录校验，拒绝把任意名称伪装成化学体系。
func communitySystemKey(db *gorm.DB, raw string) (string, error) {
	if len(raw) > 100 || raw == "" {
		return "", communityBad()
	}
	parts := strings.Split(raw, "-")
	set := map[string]bool{}
	for _, part := range parts {
		if part == "" {
			return "", communityBad()
		}
		set[part] = true
	}
	parts = parts[:0]
	for symbol := range set {
		parts = append(parts, symbol)
	}
	sort.Strings(parts)
	var symbols []string
	if err := db.Table("periodic_table_elements").Where("symbol IN ?", parts).Pluck("symbol", &symbols).Error; err != nil {
		return "", err
	}
	// MySQL 目录列可能不区分大小写，必须再按正式元素符号精确校验。
	canonical := map[string]bool{}
	for _, symbol := range symbols {
		canonical[symbol] = true
	}
	if len(symbols) != len(parts) {
		return "", communityBad()
	}
	for _, part := range parts {
		if !canonical[part] {
			return "", communityBad()
		}
	}
	return strings.Join(parts, "-"), nil
}

type communityTarget struct {
	QuestionID *uint   `json:"question_id,omitempty"`
	AnswerID   *uint   `json:"answer_id,omitempty"`
	PaperID    *uint   `json:"paper_id,omitempty"`
	SystemKey  *string `json:"system_key,omitempty"`
}

func communityTargetOf(e models.CommunityEntry) communityTarget {
	return communityTarget{e.QuestionID, e.AnswerID, e.PaperID, e.SystemKey}
}
func (t communityTarget) query(db *gorm.DB) *gorm.DB {
	if t.QuestionID != nil {
		db = db.Where("question_id = ?", *t.QuestionID)
	}
	if t.AnswerID != nil {
		db = db.Where("answer_id = ?", *t.AnswerID)
	}
	if t.PaperID != nil {
		db = db.Where("paper_id = ?", *t.PaperID)
	}
	if t.SystemKey != nil {
		db = db.Where("system_key = ?", *t.SystemKey)
	}
	return db
}
func (t *communityTarget) validate(db *gorm.DB, kind string, user *models.User) error {
	count := 0
	for _, p := range []*uint{t.QuestionID, t.AnswerID, t.PaperID} {
		if p != nil {
			if *p == 0 {
				return communityBad()
			}
			count++
		}
	}
	if t.SystemKey != nil {
		count++
	}
	if kind == "question" {
		if count != 0 {
			return communityBad()
		}
		return nil
	}
	if count != 1 {
		return communityBad()
	}
	switch kind {
	case "answer":
		if t.QuestionID == nil {
			return communityBad()
		}
	case "comment":
		if t.QuestionID != nil {
			return communityBad()
		}
	default:
		return communityBad()
	}
	if t.SystemKey != nil {
		key, err := communitySystemKey(db, *t.SystemKey)
		if err != nil {
			return err
		}
		t.SystemKey = &key
	}
	if t.PaperID != nil {
		var paper models.Paper
		if err := db.First(&paper, *t.PaperID).Error; err != nil {
			return err
		}
		if !canViewPaper(&paper, user) {
			return communityError{403, "paper_forbidden"}
		}
	}
	for _, target := range []struct {
		id   *uint
		kind string
	}{{t.QuestionID, "question"}, {t.AnswerID, "answer"}} {
		if target.id == nil {
			continue
		}
		var entry models.CommunityEntry
		if err := db.First(&entry, *target.id).Error; err != nil {
			return err
		}
		if entry.Kind != target.kind || entry.Status != "visible" {
			return gorm.ErrRecordNotFound
		}
		if err := communityAccess(db, entry, user, false); err != nil {
			return err
		}
	}
	return nil
}
func communityAccess(db *gorm.DB, entry models.CommunityEntry, user *models.User, placeholder bool) error {
	if !communitySupportedKind(entry.Kind) {
		return gorm.ErrRecordNotFound
	}
	if entry.Status != "visible" && !(placeholder && entry.Kind == "comment") {
		return gorm.ErrRecordNotFound
	}
	t := communityTargetOf(entry)
	return t.validate(db, entry.Kind, user)
}
func communitySupportedKind(kind string) bool {
	return kind == "question" || kind == "answer" || kind == "comment"
}
func communitySameTarget(a, b models.CommunityEntry) bool {
	aa, _ := json.Marshal(communityTargetOf(a))
	bb, _ := json.Marshal(communityTargetOf(b))
	return string(aa) == string(bb)
}

// 写事务先锁身份，再按论文/问题 → 答案的顺序锁目标。锁定读使用当前状态，
// 不能依赖 MySQL REPEATABLE READ 的旧快照判断隐藏、删除或论文权限。
func communityLockActor(tx *gorm.DB, user *models.User) error {
	if err := tx.Clauses(clause.Locking{Strength: "SHARE"}).First(user, user.ID).Error; err != nil {
		return err
	}
	if user.AccountStatus != "active" || !user.IsEmailVerified {
		return communityError{403, "verified_account_required"}
	}
	return nil
}

func communityCurrent(tx *gorm.DB) *gorm.DB {
	// Session 确保每次查询克隆语句，防止递归校验把不同目标的 WHERE 条件叠加。
	return tx.Clauses(clause.Locking{Strength: "SHARE"}).Session(&gorm.Session{})
}
func communityLockTarget(tx *gorm.DB, target communityTarget) error {
	if target.PaperID != nil {
		var paper models.Paper
		if err := tx.Clauses(clause.Locking{Strength: "SHARE"}).First(&paper, *target.PaperID).Error; err != nil {
			return err
		}
	}
	questionID := target.QuestionID
	if target.AnswerID != nil {
		var answer models.CommunityEntry
		if err := tx.Select("id", "question_id").First(&answer, *target.AnswerID).Error; err != nil {
			return err
		}
		questionID = answer.QuestionID
	}
	for _, id := range []*uint{questionID, target.AnswerID} {
		if id == nil {
			continue
		}
		var entry models.CommunityEntry
		if err := tx.Clauses(clause.Locking{Strength: "UPDATE"}).First(&entry, *id).Error; err != nil {
			return err
		}
	}
	return nil
}

func communityAuthor(db *gorm.DB, id uint) gin.H {
	var u models.User
	if db.First(&u, id).Error != nil || u.AccountStatus == "deactivated" {
		return gin.H{"username": "", "deactivated": true}
	}
	return gin.H{"username": u.Username, "avatar_url": avatarURL(u), "banned": u.AccountStatus == "banned"}
}
func communityURL(db *gorm.DB, e models.CommunityEntry) string {
	base := ""
	answer := e.AnswerID
	if e.Kind == "question" {
		base = fmt.Sprintf("/share/discussions/%d", e.ID)
	}
	if e.QuestionID != nil {
		base = fmt.Sprintf("/share/discussions/%d", *e.QuestionID)
	}
	if answer != nil {
		var a models.CommunityEntry
		if db.First(&a, *answer).Error == nil && a.QuestionID != nil {
			base = fmt.Sprintf("/share/discussions/%d", *a.QuestionID)
		}
	}
	if e.PaperID != nil {
		base = fmt.Sprintf("/papers/%d", *e.PaperID)
	}
	if e.SystemKey != nil {
		base = "/systems/" + *e.SystemKey
	}
	return fmt.Sprintf("%s?focus=%d#entry-%d", base, e.ID, e.ID)
}
func communityDTO(db *gorm.DB, e models.CommunityEntry, u *models.User) gin.H {
	author := gin.H(nil)
	editable := false
	if e.Status == "visible" {
		author = communityAuthor(db, e.AuthorID)
		editable = u != nil && u.ID == e.AuthorID && u.IsEmailVerified && u.AccountStatus == "active"
	} else {
		e.Body = ""
		e.Title = ""
	}
	var votes, voted, replies int64
	if e.Kind == "answer" && e.Status == "visible" {
		db.Model(&models.CommunityVote{}).Where("entry_id = ?", e.ID).Count(&votes)
		if u != nil {
			db.Model(&models.CommunityVote{}).Where("entry_id = ? AND user_id = ?", e.ID, u.ID).Count(&voted)
		}
	}
	if e.Kind == "question" {
		db.Model(&models.CommunityEntry{}).Where("question_id = ? AND kind = 'answer' AND status = 'visible'", e.ID).Count(&replies)
	}
	return gin.H{"id": e.ID, "kind": e.Kind, "title": e.Title, "body": e.Body, "status": e.Status, "author": author,
		"question_id": e.QuestionID, "answer_id": e.AnswerID, "paper_id": e.PaperID, "system_key": e.SystemKey,
		"parent_id": e.ParentID, "reply_to_id": e.ReplyToID, "votes": votes, "voted": voted > 0, "answer_count": replies,
		"can_edit": editable, "can_delete": editable, "can_reply": e.Status == "visible",
		"created_at": e.CreatedAt, "updated_at": e.UpdatedAt, "url": communityURL(db, e)}
}
