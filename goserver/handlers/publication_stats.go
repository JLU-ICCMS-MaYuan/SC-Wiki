package handlers

import (
	"net/http"
	"sort"
	"sync"
	"time"

	"scwiki/server/cache"
	"scwiki/server/database"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

const publicationCacheKey = "community:publication-stats:v1"

var publicationRefreshMu sync.Mutex

type publicationYear struct {
	Year       int   `json:"year"`
	PaperCount int64 `json:"paper_count"`
}

type publicationFamily struct {
	FamilyID         uint              `json:"family_id"`
	NameZH           string            `json:"name_zh"`
	NameEN           string            `json:"name_en"`
	PaperCount       int64             `json:"paper_count"`
	UnknownYearCount int64             `json:"unknown_year_count"`
	Years            []publicationYear `json:"years"`
}

type publicationSnapshot struct {
	Families    []publicationFamily `json:"families"`
	GeneratedAt time.Time           `json:"generated_at"`
}

// 单条语句取得目录和年度计数，避免两次读取间审核或版本变化导致总量与明细不一致。
// 不关联材料状态或物性：没有 Tc 的论文也必须被计入。
const publicationCountsSQL = `
SELECT f.id AS family_id, f.name_zh, COALESCE(f.name_en, '') AS name_en,
       counts.year, COALESCE(counts.paper_count, 0) AS paper_count
FROM material_families f
LEFT JOIN (
    SELECT pmf.material_family_id,
           CASE WHEN p.year BETWEEN 1 AND 9999 THEN p.year ELSE NULL END AS year,
           COUNT(DISTINCT p.id) AS paper_count
    FROM papers p
    JOIN paper_material_families pmf
      ON pmf.paper_id = p.id AND pmf.paper_revision = p.content_revision
    WHERE p.review_status = 'approved'
    GROUP BY pmf.material_family_id,
             CASE WHEN p.year BETWEEN 1 AND 9999 THEN p.year ELSE NULL END
) counts ON counts.material_family_id = f.id
UNION ALL
SELECT 0 AS family_id, '未分类' AS name_zh, 'Unclassified' AS name_en,
       CASE WHEN p.year BETWEEN 1 AND 9999 THEN p.year ELSE NULL END AS year,
       COUNT(DISTINCT p.id) AS paper_count
FROM papers p
WHERE p.review_status = 'approved'
  AND NOT EXISTS (
      SELECT 1 FROM paper_material_families pmf
      WHERE pmf.paper_id = p.id AND pmf.paper_revision = p.content_revision
  )
GROUP BY CASE WHEN p.year BETWEEN 1 AND 9999 THEN p.year ELSE NULL END`

func loadPublicationSnapshot(db *gorm.DB) (publicationSnapshot, error) {
	var rows []struct {
		FamilyID   uint
		NameZH     string
		NameEN     string
		Year       *int
		PaperCount int64
	}
	if err := db.Raw(publicationCountsSQL).Scan(&rows).Error; err != nil {
		return publicationSnapshot{}, err
	}
	families := map[uint]*publicationFamily{
		0: {FamilyID: 0, NameZH: "未分类", NameEN: "Unclassified", Years: []publicationYear{}},
	}
	for _, row := range rows {
		family := families[row.FamilyID]
		if family == nil {
			family = &publicationFamily{FamilyID: row.FamilyID, NameZH: row.NameZH, NameEN: row.NameEN, Years: []publicationYear{}}
			families[row.FamilyID] = family
		}
		family.PaperCount += row.PaperCount
		if row.Year == nil {
			family.UnknownYearCount += row.PaperCount
		} else {
			family.Years = append(family.Years, publicationYear{Year: *row.Year, PaperCount: row.PaperCount})
		}
	}
	snapshot := publicationSnapshot{Families: make([]publicationFamily, 0, len(families)), GeneratedAt: time.Now().UTC()}
	for _, family := range families {
		sort.Slice(family.Years, func(i, j int) bool { return family.Years[i].Year < family.Years[j].Year })
		if len(family.Years) > 1 {
			first, last := family.Years[0].Year, family.Years[len(family.Years)-1].Year
			continuous := make([]publicationYear, last-first+1)
			for i := range continuous {
				continuous[i].Year = first + i
			}
			for _, year := range family.Years {
				continuous[year.Year-first] = year
			}
			family.Years = continuous
		}
		snapshot.Families = append(snapshot.Families, *family)
	}
	sort.Slice(snapshot.Families, func(i, j int) bool {
		a, b := snapshot.Families[i], snapshot.Families[j]
		if a.PaperCount == b.PaperCount {
			return a.FamilyID < b.FamilyID
		}
		return a.PaperCount > b.PaperCount
	})
	return snapshot, nil
}

// CommunityPublicationStats 返回不含论文明细及用户身份的公开统计快照。
func CommunityPublicationStats(c *gin.Context) {
	refresh, valid := parseContributionRefresh(c.Query("refresh"))
	if !valid {
		c.JSON(http.StatusBadRequest, gin.H{"error": "refresh 必须是 true 或 false"})
		return
	}
	var snapshot publicationSnapshot
	if !refresh && cache.Get(publicationCacheKey, &snapshot) {
		c.JSON(http.StatusOK, snapshot)
		return
	}
	publicationRefreshMu.Lock()
	defer publicationRefreshMu.Unlock()
	if refresh || !cache.Get(publicationCacheKey, &snapshot) {
		var err error
		snapshot, err = loadPublicationSnapshot(database.DB.WithContext(c.Request.Context()))
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "论文统计加载失败"})
			return
		}
		cache.Set(publicationCacheKey, snapshot, time.Hour)
	}
	c.JSON(http.StatusOK, snapshot)
}
