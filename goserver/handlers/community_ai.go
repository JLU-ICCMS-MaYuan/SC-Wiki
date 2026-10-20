package handlers

import (
	"encoding/json"
	"fmt"
	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
	"scwiki/server/database"
	"scwiki/server/models"
	"strings"
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

// 前文依赖只用于可见性核验，不向客户端返回内部快照。
func communityContextAvailable(db *gorm.DB, raw json.RawMessage) bool {
	var rows []struct {
		EntryID uint `json:"entry_id"`
	}
	if len(raw) == 0 || string(raw) == "null" {
		return true
	}
	if json.Unmarshal(raw, &rows) != nil {
		return false
	}
	for _, row := range rows {
		var count int64
		if db.Model(&models.CommunityEntry{}).Where("id = ? AND status = 'visible'", row.EntryID).Count(&count).Error != nil || count != 1 {
			return false
		}
	}
	return true
}

func communityAnswerTurns(db *gorm.DB, entry models.CommunityEntry) []gin.H {
	rows := []gin.H{}
	if entry.Kind != "answer" || entry.Origin != "ai" {
		return rows
	}
	type requestInfo struct {
		Sequence        int
		ContextSnapshot json.RawMessage
	}
	first := requestInfo{}
	db.Table("community_answer_requests").Select("sequence,context_snapshot").Where("answer_id = ? AND turn_id IS NULL AND state = 'succeeded'", entry.ID).Scan(&first)
	if first.Sequence == 0 {
		db.Table("community_model_answers").Select("first_sequence AS sequence").Where("entry_id = ?", entry.ID).Scan(&first)
	}
	replies := []map[string]any{}
	var previous []map[string]any
	_ = json.Unmarshal(first.ContextSnapshot, &previous)
	for _, item := range previous {
		if key, ok := item["key"].(string); ok && strings.Contains(entry.Body, "["+key+"]") {
			replies = append(replies, map[string]any{"key": key, "model_name": item["model_name"], "sequence": item["sequence"]})
		}
	}
	available := entry.Status == "visible" && communitySourcesAvailable(db, entry.Citations) && communityContextAvailable(db, first.ContextSnapshot)
	body := entry.Body
	citations := entry.Citations
	if !available {
		body = ""
		citations = nil
		replies = nil
	}
	rows = append(rows, gin.H{"key": fmt.Sprintf("A%d", entry.ID), "id": nil, "body": body, "sequence": first.Sequence, "revision": entry.Revision, "human_edited": entry.HumanEdited, "created_at": entry.CreatedAt, "sources_available": available, "citations": communityPublicCitations(citations), "replies": replies})
	var turns []models.CommunityAnswerTurn
	db.Where("entry_id = ?", entry.ID).Order("id ASC").Find(&turns)
	for _, turn := range turns {
		info := requestInfo{}
		db.Table("community_answer_requests").Select("sequence,context_snapshot").Where("id = ?", turn.RequestID).Scan(&info)
		visible := entry.Status == "visible" && available && communitySourcesAvailable(db, turn.Citations) && communityContextAvailable(db, info.ContextSnapshot)
		body := turn.Body
		citations := turn.Citations
		replies := json.RawMessage(turn.Replies)
		if !visible {
			body = ""
			citations = nil
			replies = nil
		}
		rows = append(rows, gin.H{"key": fmt.Sprintf("A%dT%d", entry.ID, turn.ID), "id": turn.ID, "body": body, "sequence": info.Sequence, "revision": turn.Revision, "human_edited": turn.HumanEdited, "created_at": turn.CreatedAt, "sources_available": visible, "citations": communityPublicCitations(citations), "replies": replies})
	}
	return rows
}
func communityAnswerCounts(db *gorm.DB, entry models.CommunityEntry) (int64, int64) {
	if entry.Kind != "question" {
		return 0, 0
	}
	var count, turns int64
	db.Model(&models.CommunityEntry{}).Where("question_id = ? AND kind = 'answer' AND origin = 'ai' AND status = 'visible'", entry.ID).Count(&count)
	db.Table("community_answer_turns t").Joins("JOIN community_entries e ON e.id = t.entry_id").Where("e.question_id = ? AND e.status = 'visible'", entry.ID).Count(&turns)
	return count, count + turns
}
