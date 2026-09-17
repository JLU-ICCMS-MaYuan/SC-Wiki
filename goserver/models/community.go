package models

import "time"

// CommunitySystem 独立于论文版本的体系讨论空间。
type CommunitySystem struct {
	SystemKey string    `gorm:"primaryKey;size:100" json:"system_key"`
	CreatedAt time.Time `json:"created_at"`
}

// CommunityEntry 共用作者和治理规则；目标组合由社区服务严格校验。
type CommunityEntry struct {
	ID         uint      `gorm:"primaryKey" json:"id"`
	Kind       string    `gorm:"size:16;not null;index" json:"kind"`
	Title      string    `gorm:"size:200;not null" json:"title"`
	Body       string    `gorm:"type:mediumtext;not null" json:"body"`
	AuthorID   uint      `gorm:"not null;index" json:"-"`
	QuestionID *uint     `gorm:"index" json:"question_id,omitempty"`
	AnswerID   *uint     `gorm:"index" json:"answer_id,omitempty"`
	PaperID    *uint     `gorm:"index" json:"paper_id,omitempty"`
	SystemKey  *string   `gorm:"size:100;index" json:"system_key,omitempty"`
	ParentID   *uint     `gorm:"index" json:"parent_id,omitempty"`
	ReplyToID  *uint     `json:"reply_to_id,omitempty"`
	Status     string    `gorm:"size:16;not null;default:visible;index" json:"status"`
	CreatedAt  time.Time `json:"created_at"`
	UpdatedAt  time.Time `json:"updated_at"`
	ActivityAt time.Time `gorm:"index" json:"activity_at"`
}

type CommunityVote struct {
	EntryID   uint `gorm:"primaryKey"`
	UserID    uint `gorm:"primaryKey"`
	CreatedAt time.Time
}

type CommunityReport struct {
	ID         uint       `gorm:"primaryKey" json:"id"`
	EntryID    uint       `gorm:"not null;uniqueIndex:uq_community_report" json:"entry_id"`
	ReporterID uint       `gorm:"not null;uniqueIndex:uq_community_report" json:"reporter_id"`
	Reason     string     `gorm:"type:text;not null" json:"reason"`
	Status     string     `gorm:"size:16;not null;default:pending;index" json:"status"`
	CreatedAt  time.Time  `json:"created_at"`
	ResolvedAt *time.Time `json:"resolved_at"`
}

type CommunityModerationEvent struct {
	ID        uint      `gorm:"primaryKey" json:"id"`
	EntryID   uint      `gorm:"not null;index" json:"entry_id"`
	ActorID   uint      `gorm:"not null" json:"actor_id"`
	Action    string    `gorm:"size:16;not null" json:"action"`
	Reason    string    `gorm:"type:text;not null" json:"reason"`
	CreatedAt time.Time `json:"created_at"`
}

type CommunityNotification struct {
	ID          uint       `gorm:"primaryKey" json:"id"`
	RecipientID uint       `gorm:"not null;index" json:"-"`
	ActorID     uint       `gorm:"not null" json:"-"`
	EntryID     uint       `gorm:"not null;index" json:"entry_id"`
	Kind        string     `gorm:"size:16;not null" json:"kind"`
	ReadAt      *time.Time `json:"read_at"`
	CreatedAt   time.Time  `json:"created_at"`
}
