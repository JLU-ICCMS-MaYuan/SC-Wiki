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

func communityReport(c *gin.Context) {
	var body struct {
		Reason string `json:"reason"`
	}
	if err := communityBind(c, &body); err != nil {
		communityFail(c, err)
		return
	}
	body.Reason = strings.TrimSpace(body.Reason)
	if !communityLength(body.Reason, 5, 1000) {
		communityFail(c, communityBad())
		return
	}
	id, err := communityID(c.Param("id"))
	if err != nil {
		communityFail(c, err)
		return
	}
	if err = communityLimit(c, "action"); err != nil {
		communityFail(c, err)
		return
	}
	u := communityViewer(c)
	report := models.CommunityReport{EntryID: id, ReporterID: u.ID, Reason: body.Reason, Status: "pending"}
	err = database.DB.Transaction(func(tx *gorm.DB) error {
		var e models.CommunityEntry
		if err := tx.First(&e, id).Error; err != nil {
			return err
		}
		if err := communityAccess(tx, e, u, false); err != nil {
			return err
		}
		if err := tx.Clauses(clause.OnConflict{DoNothing: true}).Create(&report).Error; err != nil {
			return err
		}
		return tx.Where("entry_id = ? AND reporter_id = ?", id, u.ID).First(&report).Error
	})
	if err != nil {
		communityFail(c, err)
		return
	}
	c.JSON(200, gin.H{"id": report.ID, "status": report.Status})
}
func communityReports(c *gin.Context) {
	limit, offset, err := communityPage(c)
	if err != nil {
		communityFail(c, err)
		return
	}
	status := c.DefaultQuery("status", "pending")
	if status != "pending" && status != "resolved" {
		communityFail(c, communityBad())
		return
	}
	activeEntries := database.DB.Model(&models.CommunityEntry{}).Select("id").Where("kind IN ?", []string{"question", "answer", "comment"})
	q := database.DB.Model(&models.CommunityReport{}).Where("status = ?", status).Where("entry_id IN (?)", activeEntries)
	var total int64
	if err = q.Count(&total).Error; err != nil {
		communityFail(c, err)
		return
	}
	var reports []models.CommunityReport
	if err = q.Order("id DESC").Offset(offset).Limit(limit).Find(&reports).Error; err != nil {
		communityFail(c, err)
		return
	}
	items := []gin.H{}
	for _, report := range reports {
		var entry models.CommunityEntry
		if err = database.DB.First(&entry, report.EntryID).Error; err != nil {
			communityFail(c, err)
			return
		}
		var events []models.CommunityModerationEvent
		if err = database.DB.Where("entry_id = ?", entry.ID).Order("id DESC").Limit(20).Find(&events).Error; err != nil {
			communityFail(c, err)
			return
		}
		items = append(items, gin.H{"report": report, "entry": entry, "author": communityAuthor(database.DB, entry.AuthorID), "events": events, "url": communityURL(database.DB, entry)})
	}
	c.Header("Cache-Control", "no-store")
	c.JSON(200, gin.H{"items": items, "total": total})
}
func communityModerate(c *gin.Context) {
	var body struct {
		Action string `json:"action"`
		Reason string `json:"reason"`
	}
	if err := communityBind(c, &body); err != nil {
		communityFail(c, err)
		return
	}
	body.Reason = strings.TrimSpace(body.Reason)
	if !communityLength(body.Reason, 5, 1000) || (body.Action != "hide" && body.Action != "restore" && body.Action != "dismiss") {
		communityFail(c, communityBad())
		return
	}
	id, err := communityID(c.Param("id"))
	if err != nil {
		communityFail(c, err)
		return
	}
	if err = communityLimit(c, "action"); err != nil {
		communityFail(c, err)
		return
	}
	err = database.DB.Transaction(func(tx *gorm.DB) error {
		u := communityViewer(c)
		if err := communityLockActor(tx, u); err != nil {
			return err
		}
		if u.Role != "admin" && u.Role != "superadmin" {
			return communityError{403, "admin_required"}
		}
		var entry models.CommunityEntry
		if err := tx.First(&entry, id).Error; err != nil {
			return err
		}
		if !communitySupportedKind(entry.Kind) {
			return gorm.ErrRecordNotFound
		}
		// 管理写入与发布使用相同祖先锁顺序；恢复不要求祖先当前可见。
		if err := communityLockTarget(tx, communityTargetOf(entry)); err != nil {
			return err
		}
		if err := tx.Clauses(clause.Locking{Strength: "UPDATE"}).First(&entry, id).Error; err != nil {
			return err
		}
		if body.Action == "hide" {
			if entry.Status != "visible" {
				return communityError{409, "invalid_moderation_transition"}
			}
			entry.Status = "hidden"
		}
		if body.Action == "restore" {
			if entry.Status != "hidden" {
				return communityError{409, "invalid_moderation_transition"}
			}
			entry.Status = "visible"
		}
		if err := tx.Save(&entry).Error; err != nil {
			return err
		}
		if err := tx.Create(&models.CommunityModerationEvent{EntryID: id, ActorID: communityViewer(c).ID, Action: body.Action, Reason: body.Reason}).Error; err != nil {
			return err
		}
		return tx.Model(&models.CommunityReport{}).Where("entry_id = ? AND status = 'pending'", id).Updates(map[string]any{"status": "resolved", "resolved_at": time.Now().UTC()}).Error
	})
	if err != nil {
		communityFail(c, err)
		return
	}
	c.Status(204)
}
