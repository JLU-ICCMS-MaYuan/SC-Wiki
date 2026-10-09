package handlers

import (
	"testing"

	"scwiki/server/models"

	"github.com/DATA-DOG/go-sqlmock"
)

func TestApplyPaperEvidenceArchivesManualReasonInReviewTransaction(t *testing.T) {
	db, mock := reviewEventTestDB(t)
	paper := &models.Paper{ID: 29, ContentRevision: 2}
	item := evidenceReviewRecord{
		ItemKey: "stable-field", Field: "paper.title", ContentHash: "value-hash",
		SourceHash: "source-hash", RuleVersion: "scientific-evidence-v7",
		ManualEvidenceID: "manual-id", ManualEvidenceVersion: 3, Status: "supported",
	}
	mock.ExpectExec("INSERT INTO scientific_evidence_sources").
		WillReturnResult(sqlmock.NewResult(0, 1))
	mock.ExpectExec("UPDATE scientific_manual_evidence SET status").
		WithArgs(uint(29), uint(2), "manual-id", "29", "stable-field", 3, "value-hash", "source-hash").
		WillReturnResult(sqlmock.NewResult(0, 1))
	mock.ExpectExec("DELETE FROM scientific_evidence_checks").
		WithArgs("paper", "29").WillReturnResult(sqlmock.NewResult(0, 1))
	if err := applyPaperEvidence(db, paper, []evidenceReviewRecord{item}); err != nil {
		t.Fatal(err)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatal(err)
	}
}

func TestApplyPaperEvidenceRejectsStaleManualRecord(t *testing.T) {
	db, mock := reviewEventTestDB(t)
	paper := &models.Paper{ID: 29, ContentRevision: 2}
	item := evidenceReviewRecord{ItemKey: "stable-field", Field: "paper.title", ManualEvidenceID: "stale"}
	mock.ExpectExec("INSERT INTO scientific_evidence_sources").WillReturnResult(sqlmock.NewResult(0, 1))
	mock.ExpectExec("UPDATE scientific_manual_evidence SET status").WillReturnResult(sqlmock.NewResult(0, 0))
	if err := applyPaperEvidence(db, paper, []evidenceReviewRecord{item}); err == nil {
		t.Fatal("过期人工证据不能完成批准事务")
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatal(err)
	}
}
