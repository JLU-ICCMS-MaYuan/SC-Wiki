package handlers

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"time"

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

func newsPageParameter(c *gin.Context, name string, fallback, maximum int) (int, bool) {
	value, err := strconv.Atoi(c.DefaultQuery(name, strconv.Itoa(fallback)))
	return value, err == nil && value > 0 && value <= maximum
}

// ListNewsFeed 读取自动资讯及已有家族名称，旧人工快讯接口保持独立。
func ListNewsFeed(c *gin.Context) {
	listNewsFeedAt(c, time.Now())
}

// 使用固定北京时间偏移，避免精简容器缺少时区数据库；自然周从周一开始。
func newsWeek(now time.Time, requested string) (time.Time, time.Time, error) {
	zone := time.FixedZone("Asia/Shanghai", 8*60*60)
	local := now.In(zone)
	start := time.Date(local.Year(), local.Month(), local.Day(), 0, 0, 0, 0, zone)
	start = start.AddDate(0, 0, -(int(local.Weekday())+6)%7)
	if requested != "" {
		anchor, err := time.ParseInLocation("2006-01-02", requested, zone)
		if err != nil || anchor.Weekday() != time.Monday || anchor.After(start) {
			return time.Time{}, time.Time{}, fmt.Errorf("invalid week")
		}
		start = anchor
	}
	return start, start.AddDate(0, 0, 7), nil
}

func listNewsFeedAt(c *gin.Context, now time.Time) {
	page, validPage := newsPageParameter(c, "page", 1, 10000)
	size, validSize := newsPageParameter(c, "page_size", 20, 100)
	kind := c.Query("kind")
	period := c.DefaultQuery("period", "all") // 旧 API 消费者保持全量；页面明确传 week/history。
	weekStart, weekEnd, weekErr := newsWeek(now, c.Query("week"))
	if !validPage || !validSize || weekErr != nil || (period != "all" && period != "week" && period != "history") || (kind != "" && kind != "news" && kind != "preprint" && kind != "journal_article") {
		c.JSON(http.StatusBadRequest, gin.H{"error": "资讯查询参数不合法"})
		return
	}
	fail := func() { c.JSON(http.StatusInternalServerError, gin.H{"error": "资讯读取失败，请稍后重试"}) }
	query := database.DB.WithContext(c.Request.Context()).Model(&models.NewsFeedItem{})
	if kind != "" {
		query = query.Where("CASE WHEN display_kind = '' THEN kind ELSE display_kind END = ?", kind)
	}
	// 不把仅年/月的日期臆测为本周；历史是补集，保留所有其他已收录条目。
	withinWeek := "date_precision = 'day' AND published_at >= ? AND published_at < ?"
	if period == "week" {
		query = query.Where(withinWeek, weekStart.UTC().Format(time.RFC3339), weekEnd.UTC().Format(time.RFC3339))
	} else if period == "history" {
		query = query.Where("NOT ("+withinWeek+")", weekStart.UTC().Format(time.RFC3339), weekEnd.UTC().Format(time.RFC3339))
	}
	var total int64
	if err := query.Count(&total).Error; err != nil {
		fail()
		return
	}
	rows := make([]models.NewsFeedItem, 0)
	if err := query.Order("published_at DESC").Order("first_seen_at DESC").Order("id DESC").Limit(size).Offset((page - 1) * size).Find(&rows).Error; err != nil {
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
		item := newsFeedView{NewsFeedItem: row, Authors: []string{}, Links: []newsFeedLink{}, Notice: "自动采集，未经本站审核", MaterialFamilies: []newsFeedFamily{}}
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
	c.JSON(http.StatusOK, gin.H{"items": items, "total": total, "page": page, "page_size": size, "sources": sources,
		"period": period, "week": weekStart.Format("2006-01-02"), "week_end": weekEnd.Format("2006-01-02"), "timezone": "Asia/Shanghai"})
}
