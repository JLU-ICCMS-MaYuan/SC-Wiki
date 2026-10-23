package handlers

import (
	"github.com/gin-gonic/gin"
	"scwiki/server/database"
	"strconv"
	"strings"
	"time"
)

func contributionPagination(c *gin.Context) (int, int) {
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "20"))
	if limit < 1 {
		limit = 20
	}
	if limit > 100 {
		limit = 100
	}
	offset, _ := strconv.Atoi(c.DefaultQuery("offset", "0"))
	if offset < 0 {
		offset = 0
	}
	return limit, offset
}

// 只使用本人不可变审核事件，其他人后续复核不会抹去既有贡献。
func GetReviewedPapers(c *gin.Context) {
	user, ok := currentUserFromContext(c)
	if !ok {
		return
	}
	if user.Role != "admin" && user.Role != "superadmin" {
		c.JSON(403, gin.H{"error": "无审核权限"})
		return
	}
	limit, offset := contributionPagination(c)
	query := database.DB.Table("paper_history_events AS h").
		Joins("JOIN papers p ON p.id = h.paper_id").
		Where("h.actor_user_id = ? AND h.event_type = ?", user.ID, paperHistoryReviewed).
		Where(`NOT EXISTS (SELECT 1 FROM paper_history_events newer WHERE newer.paper_id=h.paper_id AND newer.actor_user_id=h.actor_user_id AND newer.event_type='reviewed' AND (newer.occurred_at>h.occurred_at OR (newer.occurred_at=h.occurred_at AND newer.id>h.id)))`)
	if keyword := strings.TrimSpace(c.Query("keyword")); keyword != "" {
		like := "%" + keyword + "%"
		query = query.Where("(p.title LIKE ? OR p.doi LIKE ? OR p.journal LIKE ?)", like, like, like)
	}
	if status := c.Query("review_status"); status != "" {
		query = query.Where("h.review_status = ?", status)
	}
	var total int64
	if err := query.Count(&total).Error; err != nil {
		c.JSON(500, gin.H{"error": "检查贡献加载失败"})
		return
	}
	type item struct {
		ID            uint      `json:"id"`
		Title         *string   `json:"title"`
		DOI           *string   `json:"doi"`
		Journal       *string   `json:"journal"`
		Year          *int      `json:"year"`
		ReviewStatus  string    `json:"review_status"`
		CheckedStatus string    `json:"checked_status"`
		CheckedAt     time.Time `json:"checked_at"`
	}
	items := []item{}
	if err := query.Select("p.id, p.title, p.doi, p.journal, p.year, p.review_status, h.review_status AS checked_status, h.occurred_at AS checked_at").Order("h.occurred_at DESC, h.id DESC").Limit(limit).Offset(offset).Scan(&items).Error; err != nil {
		c.JSON(500, gin.H{"error": "检查贡献加载失败"})
		return
	}
	c.JSON(200, gin.H{"items": items, "total": total, "page_size": limit})
}
