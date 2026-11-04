package handlers

import (
	"scwiki/server/models"

	"gorm.io/gorm"
)

func handoffFieldSQL(db *gorm.DB, alias, field string) string {
	value := "JSON_EXTRACT(" + alias + ".classification_snapshot, '$.handoff." + field + "')"
	if db.Dialector.Name() == "sqlite" {
		return value
	}
	return "JSON_UNQUOTE(" + value + ")"
}

func latestWorkflowIDSQL(db *gorm.DB) string {
	// 用最大事件ID定位，避免对包含整稿大JSON的行执行filesort。
	return "(SELECT MAX(latest.id) FROM paper_history_events latest WHERE latest.paper_id=papers.id AND " + handoffFieldSQL(db, "latest", "contract") + "='manuscript-handoff-v1')"
}

// 公开科学图继续由papers批准状态控制；工作稿状态仅从最新正式交接派生。
func workflowStatusSQL(db *gorm.DB) string {
	if !db.Migrator().HasTable(&models.PaperHistoryEvent{}) {
		return "papers.review_status"
	}
	return "COALESCE((SELECT CASE " + handoffFieldSQL(db, "h", "holder") + " WHEN 'author' THEN 'rejected' WHEN 'review' THEN 'pending' WHEN 'published' THEN 'approved' END FROM paper_history_events h WHERE h.id=" + latestWorkflowIDSQL(db) + "), papers.review_status)"
}

type paperWorkflowInfo struct {
	ID      uint
	Status  string  `gorm:"column:workflow_status"`
	Comment *string `gorm:"column:workflow_comment"`
}

// 一次查询当前页的小型交接头，不逐篇读取整稿快照。
func paperWorkflows(db *gorm.DB, papers []models.Paper) (map[uint]paperWorkflowInfo, error) {
	result := make(map[uint]paperWorkflowInfo, len(papers))
	if len(papers) == 0 {
		return result, nil
	}
	ids := make([]uint, 0, len(papers))
	for _, paper := range papers {
		ids = append(ids, paper.ID)
	}
	status := workflowStatusSQL(db)
	comment := "papers.review_comment"
	if status != "papers.review_status" {
		comment = "COALESCE((SELECT h.review_comment FROM paper_history_events h WHERE h.id=" + latestWorkflowIDSQL(db) + "), papers.review_comment)"
	}
	var rows []paperWorkflowInfo
	err := db.Model(&models.Paper{}).Select("papers.id, "+status+" AS workflow_status, "+comment+" AS workflow_comment").Where("papers.id IN ?", ids).Scan(&rows).Error
	for _, row := range rows {
		result[row.ID] = row
	}
	return result, err
}
