package handlers

import (
	"encoding/json"
	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
	"scwiki/server/database"
	"scwiki/server/models"
)

func communityReadOnly(c *gin.Context) { communityFail(c, communityError{403, "community_read_only"}) }

type communityCitation struct {
	ID            string `json:"id"`
	PaperID       uint   `json:"paper_id"`
	PaperRevision int    `json:"paper_revision"`
	Title         string `json:"title"`
	Cited         *bool  `json:"cited,omitempty"`
}

func communityPublicCitations(raw json.RawMessage) []communityCitation {
	all := []communityCitation{}
	_ = json.Unmarshal(raw, &all)
	rows := []communityCitation{}
	for _, source := range all {
		if source.Cited == nil || *source.Cited {
			rows = append(rows, source)
		}
	}
	return rows
}
func communitySourcesAvailable(db *gorm.DB, raw json.RawMessage) bool {
	if len(raw) == 0 || string(raw) == "null" {
		return true
	}
	var rows []communityCitation
	if json.Unmarshal(raw, &rows) != nil {
		return false
	}
	for _, source := range rows {
		var count int64
		if db.Model(&models.Paper{}).Where("id = ? AND review_status = 'approved' AND content_revision = ? AND approved_revision = content_revision", source.PaperID, source.PaperRevision).Count(&count).Error != nil || count != 1 {
			return false
		}
	}
	return true
}

type communityTaskDTO struct {
	BatchID    string `json:"batch_id"`
	ID         uint   `json:"id"`
	ModelID    string `json:"model_id"`
	ModelName  string `json:"model_name"`
	Model      string `json:"model"`
	ModelOrder int    `json:"model_order"`
	State      string `json:"state"`
	Error      string `json:"error"`
	AnswerID   *uint  `json:"answer_id"`
}

func communityGenerationTasks(db *gorm.DB, entry models.CommunityEntry) []communityTaskDTO {
	rows := []communityTaskDTO{}
	// 迁移前的历史数据没有新版来源值，不查询尚不存在的任务表。
	if entry.Kind != "question" || entry.Origin == "" {
		return rows
	}
	db.Table("community_ai_tasks AS t").Select("t.id,t.batch_id,t.model_id,t.model_name,t.model,t.model_order,t.state,t.error,t.answer_id").Joins("JOIN community_ai_batches b ON b.id = t.batch_id").Where("b.question_id = ?", entry.ID).Order("t.model_order ASC").Scan(&rows)
	return rows
}
func communityManagedEntries(c *gin.Context) {
	limit, offset, err := communityPage(c)
	if err != nil {
		communityFail(c, err)
		return
	}
	status := c.DefaultQuery("status", "hidden")
	if status != "hidden" && status != "visible" {
		communityFail(c, communityBad())
		return
	}
	q := database.DB.Model(&models.CommunityEntry{}).Where("status = ? AND kind IN ?", status, []string{"question", "answer", "comment"})
	communityList(c, q, "id DESC", limit, offset)
}
