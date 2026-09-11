package handlers

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"gorm.io/gorm"
	"scwiki/server/models"
)

// 模型仅提供语义建议；候选来自 Python 当前版本的确定性原文复核。
type evidenceCitation struct {
	ChunkID   uint    `json:"chunk_id"`
	Quote     string  `json:"quote"`
	Section   *string `json:"section"`
	PageStart *int    `json:"page_start"`
	PageEnd   *int    `json:"page_end"`
}
type evidenceReviewRecord struct {
	Key         string             `json:"key"`
	RecordID    uint               `json:"record_id"`
	Field       string             `json:"field"`
	Label       string             `json:"label"`
	ContentHash string             `json:"content_hash"`
	SourceHash  string             `json:"source_hash"`
	RuleVersion string             `json:"rule_version"`
	Status      string             `json:"status"`
	Reason      string             `json:"reason"`
	Model       string             `json:"model"`
	Resolution  string             `json:"resolution"`
	Evidences   []evidenceCitation `json:"evidences"`
}
type evidencePrepareError struct {
	Status int
	Detail json.RawMessage
}

func (e *evidencePrepareError) Error() string { return "证据核对未完成" }

var evidencePrepareClient = &http.Client{Timeout: 20 * time.Second}

func preparePaperEvidence(tx *gorm.DB, paper *models.Paper, auth, jobID, version string, resolutions map[string]string) ([]evidenceReviewRecord, error) {
	var count int64
	if err := tx.Model(&models.PropertyRecord{}).Where("paper_id = ? AND paper_revision = ?", paper.ID, paper.ContentRevision).Count(&count).Error; err != nil {
		return nil, err
	}
	if count == 0 {
		return nil, nil
	}
	if resolutions == nil {
		resolutions = map[string]string{}
	}
	raw, err := json.Marshal(map[string]interface{}{"paper_id": paper.ID, "job_id": optionalString(jobID), "expected_version": optionalString(version), "resolutions": resolutions})
	if err != nil {
		return nil, err
	}
	req, err := http.NewRequest(http.MethodPost, strings.TrimRight(pythonBackendURL(), "/")+"/api/rag/evidence/prepare-review", bytes.NewReader(raw))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", auth)
	req.Header.Set("Content-Type", "application/json")
	resp, err := evidencePrepareClient.Do(req)
	if err != nil {
		return nil, &evidencePrepareError{502, json.RawMessage(`{"code":"evidence_service_unavailable","message":"证据核对服务暂不可用，审核未提交，请重试"}`)}
	}
	defer resp.Body.Close()
	data, err := io.ReadAll(io.LimitReader(resp.Body, 8*1024*1024))
	if err != nil {
		return nil, err
	}
	if resp.StatusCode != 200 {
		var envelope struct {
			Detail json.RawMessage `json:"detail"`
		}
		if json.Unmarshal(data, &envelope) != nil || len(envelope.Detail) == 0 {
			envelope.Detail = json.RawMessage(`{"code":"evidence_service_unavailable","message":"证据核对服务异常，审核未提交"}`)
		}
		return nil, &evidencePrepareError{resp.StatusCode, envelope.Detail}
	}
	var result struct {
		Records []evidenceReviewRecord `json:"records"`
	}
	if err := json.Unmarshal(data, &result); err != nil {
		return nil, err
	}
	if int64(len(result.Records)) != count {
		return nil, errors.New("证据核对结果缺少记录")
	}
	seen := map[uint]bool{}
	for _, r := range result.Records {
		if seen[r.RecordID] || len(r.Evidences) == 0 || (r.Status != "supported" && strings.TrimSpace(r.Resolution) == "") {
			return nil, errors.New("证据核对结果无效")
		}
		seen[r.RecordID] = true
		var record models.PropertyRecord
		if err := tx.Where("id = ? AND paper_id = ? AND paper_revision = ?", r.RecordID, paper.ID, paper.ContentRevision).First(&record).Error; err != nil {
			return nil, err
		}
	}
	return result.Records, nil
}

func optionalString(value string) interface{} {
	if value == "" {
		return nil
	}
	return value
}

// 调用方已锁论文行；证据、核对记录和批准历史一同提交或回滚。
func applyPaperEvidence(tx *gorm.DB, paper *models.Paper, records []evidenceReviewRecord) error {
	for _, r := range records {
		if err := tx.Where("record_id = ?", r.RecordID).Delete(&models.PropertyRecordEvidence{}).Error; err != nil {
			return err
		}
		for _, e := range r.Evidences {
			var chunk models.PaperChunk
			if err := tx.Where("id = ? AND paper_id = ? AND paper_revision = ?", e.ChunkID, paper.ID, paper.ContentRevision).First(&chunk).Error; err != nil {
				return err
			}
			if strings.TrimSpace(e.Quote) == "" {
				return errors.New("原文引句不能为空")
			}
			evidence := models.PaperEvidence{PaperID: paper.ID, PaperRevision: paper.ContentRevision, PaperChunkID: e.ChunkID, FieldPath: r.Field, Quote: e.Quote, Section: e.Section, PageStart: e.PageStart, PageEnd: e.PageEnd}
			// 幂等复用相同来源快照，避免每次审核复制永久证据。
			query := tx.Where("paper_id = ? AND paper_revision = ? AND paper_chunk_id = ? AND field_path = ? AND quote = ?", paper.ID, paper.ContentRevision, e.ChunkID, r.Field, e.Quote).First(&evidence)
			if errors.Is(query.Error, gorm.ErrRecordNotFound) {
				if err := tx.Create(&evidence).Error; err != nil {
					return err
				}
			} else if query.Error != nil {
				return query.Error
			}
			link := models.PropertyRecordEvidence{RecordID: uint64(r.RecordID), PaperEvidenceID: evidence.ID, PaperID: paper.ID, PaperRevision: paper.ContentRevision, FieldPath: r.Field, EvidenceRole: "primary"}
			if err := tx.Create(&link).Error; err != nil {
				return err
			}
		}
		snapshot, err := json.Marshal(r.Evidences)
		if err != nil {
			return err
		}
		if err := tx.Exec(`INSERT INTO property_evidence_checks (paper_id,paper_revision,record_id,content_hash,source_hash,rule_version,status,reason,model,evidence_snapshot) VALUES (?,?,?,?,?,?,?,?,?,?)`, paper.ID, paper.ContentRevision, r.RecordID, r.ContentHash, r.SourceHash, r.RuleVersion, r.Status, r.Reason, r.Model, string(snapshot)).Error; err != nil {
			return fmt.Errorf("保存核对结果失败: %w", err)
		}
	}
	return nil
}
