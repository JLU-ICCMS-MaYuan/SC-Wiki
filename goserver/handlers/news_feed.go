package handlers

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"scwiki/server/database"
	"scwiki/server/models"
)

type newsFeedLink struct {
	Source string `json:"source"`
	URL    string `json:"url"`
}

type newsFeedView struct {
	models.NewsFeedItem
	Authors            []string         `json:"authors"`
	Links              []newsFeedLink   `json:"links"`
	Notice             string           `json:"notice"`
	PaperType          *string          `json:"paper_type"`
	TheoreticalSubtype *string          `json:"theoretical_subtype"`
	MaterialFamilies   []newsFeedFamily `json:"material_families"`
}

type newsFeedFamily struct {
	ItemID string `json:"-"`
	ID     uint   `json:"id"`
	NameZh string `json:"name_zh"`
	NameEn string `json:"name_en"`
}

// 内容决定分栏；display_kind 不再允许将科研报道放进期刊。与 Python content_kind 保持一致。
const newsContentKind = "CASE WHEN kind = 'news' OR content_type IN ('research_report','social_industry') OR source IN ('physorg','google_news') OR doi LIKE '10.1038/d41586-%' OR doi LIKE '10.1038/news.%' OR doi LIKE '10.1103/physics.%' OR doi LIKE '10.1021/cen-%' OR url LIKE 'http%://physics.aps.org/%' OR url LIKE 'http%://cen.acs.org/%' OR url LIKE 'http%://www.science.org/content/article/%' OR url LIKE 'http%://www.science.org/news/%' OR url LIKE 'http%://www.sciencemag.org/content/article/%' OR url LIKE 'http%://www.sciencemag.org/news/%' OR url LIKE 'http%://www.nature.com/news/%' THEN 'news' WHEN kind = 'preprint' THEN 'preprint' ELSE 'journal_article' END"

type newsFeedRow struct {
	models.NewsFeedItem
	EffectiveKind string
}

func newsPageParameter(c *gin.Context, name string, fallback, maximum int) (int, bool) {
	value, err := strconv.Atoi(c.DefaultQuery(name, strconv.Itoa(fallback)))
	return value, err == nil && value > 0 && value <= maximum
}

// ListNewsFeed 读取自动资讯及已有家族名称，旧人工快讯接口保持独立。
func ListNewsFeed(c *gin.Context) {
	page, validPage := newsPageParameter(c, "page", 1, 10000)
	size, validSize := newsPageParameter(c, "page_size", 20, 100)
	kind := c.Query("kind")
	// 日期范围已退役；旧调用附带的 period/week 与其他未使用参数一样忽略。
	if !validPage || !validSize || (kind != "" && kind != "news" && kind != "preprint" && kind != "journal_article") {
		c.JSON(http.StatusBadRequest, gin.H{"error": "资讯查询参数不合法"})
		return
	}
	fail := func() { c.JSON(http.StatusInternalServerError, gin.H{"error": "资讯读取失败，请稍后重试"}) }
	query := database.DB.WithContext(c.Request.Context()).Model(&models.NewsFeedItem{})
	if kind != "" {
		query = query.Where(newsContentKind+" = ?", kind)
	}
	var total int64
	if err := query.Count(&total).Error; err != nil {
		fail()
		return
	}
	rows := make([]newsFeedRow, 0)
	if err := query.Select("news_feed_items.*, " + newsContentKind + " AS effective_kind").Order("published_at DESC").Order("first_seen_at DESC").Order("id DESC").Limit(size).Offset((page - 1) * size).Find(&rows).Error; err != nil {
		fail()
		return
	}
	items := make([]newsFeedView, 0, len(rows))
	ids := make([]string, 0, len(rows))
	for _, row := range rows {
		ids = append(ids, row.ID)
	}
	classifications := make(map[string]models.NewsFeedClassification)
	families := make(map[string][]newsFeedFamily)
	if len(ids) > 0 {
		var results []models.NewsFeedClassification
		if err := database.DB.WithContext(c.Request.Context()).Where("item_id IN ? AND status = ?", ids, "completed").Find(&results).Error; err != nil {
			fail()
			return
		}
		for _, result := range results {
			classifications[result.ItemID] = result
		}
		var links []newsFeedFamily
		if err := database.DB.WithContext(c.Request.Context()).Table("news_feed_material_families AS links").
			Select("links.item_id, family.id, family.name_zh, COALESCE(family.name_en, '') AS name_en").
			Joins("JOIN material_families AS family ON family.id = links.material_family_id").
			Where("links.item_id IN ?", ids).Order("family.id").Scan(&links).Error; err != nil {
			fail()
			return
		}
		for _, family := range links {
			families[family.ItemID] = append(families[family.ItemID], family)
		}
	}
	for _, row := range rows {
		row.Kind, row.DisplayKind = row.EffectiveKind, row.EffectiveKind
		if row.Kind == "news" && row.ContentType != "social_industry" {
			row.ContentType = "research_report"
		}
		if row.Kind == "journal_article" {
			row.ContentType = "journal_article"
		}
		item := newsFeedView{NewsFeedItem: row.NewsFeedItem, Authors: []string{}, Links: []newsFeedLink{}, Notice: "自动采集，未经本站审核", MaterialFamilies: []newsFeedFamily{}}
		if result, ok := classifications[row.ID]; ok && result.ContentHash == fmt.Sprintf("%x", sha256.Sum256([]byte(row.Title+"\x00"+row.Summary))) {
			item.PaperType = result.PaperType
			if result.PaperType != nil && *result.PaperType == "theoretical" {
				item.TheoreticalSubtype = result.TheoreticalSubtype
			}
			if len(families[row.ID]) > 0 {
				item.MaterialFamilies = families[row.ID]
			}
		}
		if json.Unmarshal([]byte(row.Authors), &item.Authors) != nil || json.Unmarshal([]byte(row.Links), &item.Links) != nil {
			fail()
			return
		}
		if item.Authors == nil {
			item.Authors = []string{}
		}
		if item.Links == nil {
			item.Links = []newsFeedLink{}
		}
		items = append(items, item)
	}
	states := make([]models.NewsFeedSource, 0)
	if err := database.DB.WithContext(c.Request.Context()).Find(&states).Error; err != nil {
		fail()
		return
	}
	sources := make([]models.NewsFeedSource, 0, 3)
	for _, candidate := range states {
		if candidate.Source != "" {
			sources = append(sources, candidate)
		}
	}
	for _, name := range []string{"arxiv", "crossref", "openalex", "aps", "acs", "nature", "science", "nsr", "cpl", "cpb", "materials_today", "physorg", "google_news"} {
		found := false
		for _, candidate := range sources {
			if candidate.Source == name {
				found = true
				break
			}
		}
		if found {
			continue
		}
		state := models.NewsFeedSource{Source: name, Status: "never"}
		sources = append(sources, state)
	}
	c.Header("Cache-Control", "no-store")
	c.JSON(http.StatusOK, gin.H{"items": items, "total": total, "page": page, "page_size": size, "sources": sources})
}
