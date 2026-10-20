package handlers

import (
	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
	"scwiki/server/database"
	"scwiki/server/models"
	"strings"
	"time"
)

func communityQuestions(c *gin.Context) {
	limit, offset, err := communityPage(c)
	if err != nil {
		communityFail(c, err)
		return
	}
	q := database.DB.Model(&models.CommunityEntry{}).Where("kind = 'question' AND status = 'visible'")
	term := strings.TrimSpace(c.Query("q"))
	if !communityLength(term, 0, 200) {
		communityFail(c, communityBad())
		return
	}
	if term != "" {
		q = q.Where("title LIKE ? OR body LIKE ?", "%"+term+"%", "%"+term+"%")
	}
	order := "id DESC"
	switch c.DefaultQuery("sort", "latest") {
	case "latest":
	case "active":
		order = "activity_at DESC, id DESC"
	default:
		communityFail(c, communityBad())
		return
	}
	communityList(c, q, order, limit, offset)
}

func communityTargetQuery(c *gin.Context) (communityTarget, error) {
	t := communityTarget{}
	for key, dest := range map[string]**uint{"question_id": &t.QuestionID, "answer_id": &t.AnswerID, "paper_id": &t.PaperID} {
		if raw, exists := c.GetQuery(key); exists {
			id, err := communityID(raw)
			if err != nil {
				return t, err
			}
			*dest = &id
		}
	}
	if key, exists := c.GetQuery("system_key"); exists {
		t.SystemKey = &key
	}
	return t, nil
}
func communityEntries(c *gin.Context) {
	limit, offset, err := communityPage(c)
	if err != nil {
		communityFail(c, err)
		return
	}
	t, err := communityTargetQuery(c)
	if err != nil {
		communityFail(c, err)
		return
	}
	kind := c.Query("kind")
	if kind == "question" {
		communityFail(c, communityBad())
		return
	}
	if err = t.validate(database.DB, kind, communityViewer(c)); err != nil {
		communityFail(c, err)
		return
	}
	q := t.query(database.DB.Model(&models.CommunityEntry{})).Where("kind = ?", kind)
	if kind != "comment" {
		q = q.Where("status = 'visible'")
	}
	order := "id ASC"
	var focusedComment uint
	if kind == "comment" {
		order = "COALESCE(parent_id, id) ASC, id ASC"
	}
	if kind == "answer" {
		switch c.DefaultQuery("sort", "votes") {
		case "models":
			order = "model_order ASC, id ASC"
		case "votes":
			order = "(SELECT COUNT(*) FROM community_votes WHERE entry_id = community_entries.id) DESC, id ASC"
		case "latest":
			order = "id DESC"
		default:
			communityFail(c, communityBad())
			return
		}
	}
	// 通知定位只展示目标答案或评论线程；普通列表仍正常分页。
	if raw := c.Query("focus_id"); raw != "" {
		id, parseErr := communityID(raw)
		if parseErr != nil {
			communityFail(c, parseErr)
			return
		}
		var focus models.CommunityEntry
		if err = database.DB.First(&focus, id).Error; err != nil {
			communityFail(c, err)
			return
		}
		if err = communityAccess(database.DB, focus, communityViewer(c), true); err != nil {
			communityFail(c, err)
			return
		}
		if kind == "answer" && focus.AnswerID != nil {
			q = q.Where("id = ?", *focus.AnswerID)
		} else if kind == "answer" && focus.Kind == "answer" {
			q = q.Where("id = ?", focus.ID)
		} else if kind == "comment" && focus.Kind == "comment" {
			focusedComment = focus.ID
			root := focus.ID
			if focus.ParentID != nil {
				root = *focus.ParentID
			}
			q = q.Where("id = ? OR parent_id = ?", root, root)
		}
	}
	if kind == "comment" {
		communityCommentList(c, q, order, limit, offset, focusedComment)
		return
	}
	communityList(c, q, order, limit, offset)
}

// 评论按根线程排序；跨页时附根评论上下文，通知首次读取自动定位目标所在页。
func communityCommentList(c *gin.Context, q *gorm.DB, order string, limit, offset int, focus uint) {
	if _, explicit := c.GetQuery("offset"); focus != 0 && !explicit {
		var preceding int64
		if err := q.Session(&gorm.Session{}).Where("id < ?", focus).Count(&preceding).Error; err != nil {
			communityFail(c, err)
			return
		}
		offset = int(preceding) / limit * limit
	}
	var total int64
	if err := q.Count(&total).Error; err != nil {
		communityFail(c, err)
		return
	}
	var entries []models.CommunityEntry
	if err := q.Order(order).Limit(limit).Offset(offset).Find(&entries).Error; err != nil {
		communityFail(c, err)
		return
	}
	items, context := []gin.H{}, []gin.H{}
	present, needed := map[uint]bool{}, map[uint]bool{}
	for _, entry := range entries {
		present[entry.ID] = true
		if entry.ParentID != nil {
			needed[*entry.ParentID] = true
		}
		items = append(items, communityDTO(database.DB, entry, communityViewer(c)))
	}
	for id := range needed {
		if present[id] {
			continue
		}
		var root models.CommunityEntry
		if err := database.DB.First(&root, id).Error; err != nil {
			communityFail(c, err)
			return
		}
		if err := communityAccess(database.DB, root, communityViewer(c), true); err != nil {
			communityFail(c, err)
			return
		}
		context = append(context, communityDTO(database.DB, root, communityViewer(c)))
	}
	c.Header("Cache-Control", "no-store")
	c.JSON(200, gin.H{"items": items, "context": context, "total": total, "offset": offset})
}
func communityList(c *gin.Context, q *gorm.DB, order string, limit, offset int) {
	var total int64
	if err := q.Count(&total).Error; err != nil {
		communityFail(c, err)
		return
	}
	var entries []models.CommunityEntry
	if err := q.Order(order).Limit(limit).Offset(offset).Find(&entries).Error; err != nil {
		communityFail(c, err)
		return
	}
	items := make([]gin.H, 0, len(entries))
	for _, entry := range entries {
		items = append(items, communityDTO(database.DB, entry, communityViewer(c)))
	}
	c.Header("Cache-Control", "no-store")
	c.JSON(200, gin.H{"items": items, "total": total})
}
func communityGetEntry(c *gin.Context) {
	id, err := communityID(c.Param("id"))
	if err != nil {
		communityFail(c, err)
		return
	}
	var entry models.CommunityEntry
	if err = database.DB.First(&entry, id).Error; err == nil {
		err = communityAccess(database.DB, entry, communityViewer(c), true)
	}
	if err != nil {
		communityFail(c, err)
		return
	}
	c.Header("Cache-Control", "no-store")
	c.JSON(200, communityDTO(database.DB, entry, communityViewer(c)))
}

func communityEdit(c *gin.Context) {
	var body struct {
		Body     string `json:"body"`
		Revision int    `json:"revision"`
	}
	if err := communityBind(c, &body); err != nil {
		communityFail(c, err)
		return
	}
	body.Body = strings.TrimSpace(body.Body)
	if !communityLength(body.Body, 1, 20000) || body.Revision < 1 {
		communityFail(c, communityBad())
		return
	}
	id, err := communityID(c.Param("id"))
	if err != nil {
		communityFail(c, err)
		return
	}
	u := communityViewer(c)
	var entry models.CommunityEntry
	err = database.DB.Transaction(func(tx *gorm.DB) error {
		if err := communityLockActor(tx, u); err != nil {
			return err
		}
		if u.Role != "superadmin" {
			return communityError{403, "superadmin_required"}
		}
		if err := tx.First(&entry, id).Error; err != nil {
			return err
		}
		if err := communityLockTarget(tx, communityTargetOf(entry)); err != nil {
			return err
		}
		if err := tx.Clauses(clause.Locking{Strength: "UPDATE"}).First(&entry, id).Error; err != nil {
			return err
		}
		if entry.Kind != "answer" {
			return communityError{403, "community_read_only"}
		}
		if err := communityAccess(communityCurrent(tx), entry, u, false); err != nil {
			return err
		}
		if entry.Revision != body.Revision {
			return communityError{409, "community_revision_conflict"}
		}
		if err := tx.Create(&models.CommunityEntryRevision{EntryID: entry.ID, Revision: entry.Revision, Body: entry.Body, Citations: entry.Citations, HumanEdited: entry.HumanEdited, ActorID: &u.ID}).Error; err != nil {
			return err
		}
		entry.Body = body.Body
		entry.HumanEdited = true
		entry.Revision++
		entry.UpdatedAt = time.Now().UTC()
		return tx.Model(&entry).Updates(map[string]any{"body": entry.Body, "human_edited": true, "revision": entry.Revision, "updated_at": entry.UpdatedAt}).Error
	})
	if err != nil {
		communityFail(c, err)
		return
	}
	c.JSON(200, communityDTO(database.DB, entry, u))
}

func communitySystem(c *gin.Context) {
	key, err := communitySystemKey(database.DB, c.Param("key"))
	if err != nil {
		communityFail(c, err)
		return
	}
	limit, offset, err := communityPage(c)
	if err != nil {
		communityFail(c, err)
		return
	}
	// 仅依赖论文与体系关联，不要求论文必须含有 Tc 记录。
	q := database.DB.Table("papers").Where("review_status = 'approved'").Where("EXISTS (SELECT 1 FROM chemical_systems cs WHERE cs.paper_id = papers.id AND cs.paper_revision = papers.content_revision AND cs.system_key = ?)", key)
	var total int64
	if err = q.Count(&total).Error; err != nil {
		communityFail(c, err)
		return
	}
	var papers []struct {
		ID    uint    `json:"id"`
		Title string  `json:"title"`
		Year  *int    `json:"year"`
		DOI   *string `json:"doi"`
	}
	if err = q.Select("id,title,year,doi").Order("year DESC, id DESC").Limit(limit).Offset(offset).Scan(&papers).Error; err != nil {
		communityFail(c, err)
		return
	}
	if papers == nil {
		papers = make([]struct {
			ID    uint    `json:"id"`
			Title string  `json:"title"`
			Year  *int    `json:"year"`
			DOI   *string `json:"doi"`
		}, 0)
	}
	c.JSON(200, gin.H{"system_key": key, "elements": strings.Split(key, "-"), "papers": papers, "total": total})
}
