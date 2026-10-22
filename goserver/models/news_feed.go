package models

// NewsFeedItem 为 Python 写入的自动资讯，不能作为正式论文记录使用。
type NewsFeedItem struct {
	ID                string `gorm:"primaryKey;size:32" json:"id"`
	Kind              string `gorm:"size:24" json:"kind"`
	Title             string `json:"title"`
	Summary           string `json:"summary"`
	SummarySource     string `json:"summary_source"`
	Source            string `json:"source"`
	URL               string `json:"url"`
	DOI               string `json:"doi"`
	ArxivID           string `json:"arxiv_id"`
	Version           int    `json:"version"`
	Authors           string `json:"-"`
	Journal           string `json:"journal"`
	Links             string `json:"-"`
	PublishedAt       string `json:"published_at"`
	DatePrecision     string `json:"date_precision"`
	SourceUpdatedAt   string `json:"source_updated_at"`
	ContentType       string `json:"content_type"`
	DisplayKind       string `json:"display_kind"`
	DiscoverySource   string `json:"discovery_source"`
	OriginalSource    string `json:"original_source"`
	RelevanceEvidence string `json:"relevance_evidence"`
	FirstSeenAt       string `json:"first_seen_at"`
	LastSeenAt        string `json:"last_seen_at"`
}

type NewsFeedSource struct {
	Source         string `gorm:"primaryKey;size:16" json:"source"`
	Status         string `json:"status"`
	LastStartedAt  string `json:"last_started_at"`
	LastFinishedAt string `json:"last_finished_at"`
	LastSuccessAt  string `json:"last_success_at"`
	ErrorCode      string `json:"error_code"`
	Fetched        int    `json:"fetched"`
	Accepted       int    `json:"accepted"`
}

// 分类结果只用于自动资讯，不代表正式论文审核。
type NewsFeedClassification struct {
	ItemID             string `gorm:"primaryKey;size:32"`
	PaperType          *string
	TheoreticalSubtype *string
	ContentHash        string
	CatalogHash        string
	RuleVersion        string
	Model              string
	Reason             string
	Status             string
	Attempts           int
	AttemptToken       string
	UpdatedAt          string
}

type NewsFeedMaterialFamily struct {
	ItemID           string `gorm:"primaryKey;size:32"`
	MaterialFamilyID uint   `gorm:"primaryKey"`
}
