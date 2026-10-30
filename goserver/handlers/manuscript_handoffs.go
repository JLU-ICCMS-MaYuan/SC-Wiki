package handlers

import (
	"errors"
	"fmt"
	driver "github.com/go-sql-driver/mysql"
	"gorm.io/gorm"
	"strings"
)

// 新正式交接或已开启的工作稿只能经工作稿服务写入。
func paperUsesHandoffs(tx *gorm.DB, paperID uint) bool {
	var count int64
	result := tx.Table("paper_history_events").Where("paper_id = ? AND JSON_EXTRACT(classification_snapshot, '$.handoff.contract') = ?", paperID, "manuscript-handoff-v1").Count(&count)
	if result.Error != nil || count > 0 {
		return true
	}
	result = tx.Table("scientific_work_drafts").Where("target = ? AND target_id = ?", "paper", fmt.Sprint(paperID)).Count(&count)
	if result.Error != nil {
		var missing *driver.MySQLError
		if errors.As(result.Error, &missing) && missing.Number == 1146 {
			return false
		}
		if strings.Contains(result.Error.Error(), "no such table: scientific_work_drafts") {
			return false
		}
		return true
	}
	return count > 0
}
