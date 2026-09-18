package handlers

import (
	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
	"scwiki/server/database"
	"scwiki/server/models"
	"time"
)

// 与发布共用事务；不会出现发布失败但通知成功的情况。
func communityNotify(tx *gorm.DB, e models.CommunityEntry) error {
	ids := []*uint{}
	kind := e.Kind
	if e.Kind == "answer" {
		ids = append(ids, e.QuestionID)
	}
	if e.Kind == "comment" {
		if e.ReplyToID != nil {
			ids = append(ids, e.ReplyToID)
			kind = "reply"
		} else if e.AnswerID != nil {
			ids = append(ids, e.AnswerID)
		}
	}
	recipients := map[uint]bool{}
	for _, id := range ids {
		if id == nil {
			continue
		}
		var parent models.CommunityEntry
		if err := tx.First(&parent, *id).Error; err != nil {
			return err
		}
		if parent.AuthorID != e.AuthorID {
			recipients[parent.AuthorID] = true
		}
	}
	for recipient := range recipients {
		if err := tx.Create(&models.CommunityNotification{RecipientID: recipient, ActorID: e.AuthorID, EntryID: e.ID, Kind: kind}).Error; err != nil {
			return err
		}
	}
	return nil
}

type communityVisibleNotice struct {
	notice models.CommunityNotification
	entry  models.CommunityEntry
}

func communityVisibleNotifications(user *models.User, unread bool) ([]communityVisibleNotice, error) {
	result := []communityVisibleNotice{}
	query := database.DB.Model(&models.CommunityNotification{}).Where("recipient_id = ?", user.ID)
	if unread {
		query = query.Where("read_at IS NULL")
	}
	// 权限统一由 communityAccess 判断，避免将论文规则复制进通知 SQL。
	var notices []models.CommunityNotification
	if err := query.Order("id DESC").Find(&notices).Error; err != nil {
		return nil, err
	}
	for _, notice := range notices {
		var entry models.CommunityEntry
		if err := database.DB.First(&entry, notice.EntryID).Error; err != nil {
			if err == gorm.ErrRecordNotFound {
				continue
			}
			return nil, err
		}
		if err := communityAccess(database.DB, entry, user, false); err != nil {
			if err == gorm.ErrRecordNotFound {
				continue
			}
			if problem, ok := err.(communityError); ok && problem.status == 403 {
				continue
			}
			return nil, err
		}
		result = append(result, communityVisibleNotice{notice, entry})
	}
	return result, nil
}
func communityNotifications(c *gin.Context) {
	limit, offset, err := communityPage(c)
	if err != nil {
		communityFail(c, err)
		return
	}
	rows, err := communityVisibleNotifications(communityViewer(c), false)
	if err != nil {
		communityFail(c, err)
		return
	}
	items := []gin.H{}
	end := offset + limit
	if end > len(rows) {
		end = len(rows)
	}
	for i := offset; i < end; i++ {
		row := rows[i]
		items = append(items, gin.H{"id": row.notice.ID, "kind": row.notice.Kind, "entry_id": row.entry.ID, "actor": communityAuthor(database.DB, row.notice.ActorID), "read_at": row.notice.ReadAt, "created_at": row.notice.CreatedAt, "url": communityURL(database.DB, row.entry)})
	}
	c.Header("Cache-Control", "no-store")
	c.JSON(200, gin.H{"items": items, "total": len(rows)})
}
func communityUnread(c *gin.Context) {
	rows, err := communityVisibleNotifications(communityViewer(c), true)
	if err != nil {
		communityFail(c, err)
		return
	}
	c.Header("Cache-Control", "no-store")
	c.JSON(200, gin.H{"count": len(rows)})
}
func communityReadNotifications(c *gin.Context) {
	var body struct {
		ID *uint `json:"id"`
	}
	if err := communityBind(c, &body); err != nil {
		communityFail(c, err)
		return
	}
	query := database.DB.Model(&models.CommunityNotification{}).Where("recipient_id = ? AND read_at IS NULL", communityViewer(c).ID)
	if body.ID != nil {
		if *body.ID == 0 {
			communityFail(c, communityBad())
			return
		}
		query = query.Where("id = ?", *body.ID)
	}
	if err := query.Update("read_at", time.Now().UTC()).Error; err != nil {
		communityFail(c, err)
		return
	}
	c.Status(204)
}
