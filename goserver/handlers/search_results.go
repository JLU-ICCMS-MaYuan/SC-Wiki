package handlers

import (
	"fmt"
	"net/http"
	"sort"
	"strings"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
	"scwiki/server/database"
)

type searchResultsRequest struct {
	Elements           []string `json:"elements"`
	Mode               string   `json:"mode"`
	Formula            string   `json:"formula"`
	Keyword            string   `json:"keyword"`
	View               string   `json:"view"`
	Limit              int      `json:"limit"`
	Offset             int      `json:"offset"`
	PressureMin        *float64 `json:"pressure_min"`
	PressureMax        *float64 `json:"pressure_max"`
	YearMin            *int     `json:"year_min"`
	YearMax            *int     `json:"year_max"`
	TcMin              *float64 `json:"tc_min"`
	TcMax              *float64 `json:"tc_max"`
	ChartOnly          bool     `json:"chart_only"`
	SuperconductorType string   `json:"superconductor_type"`
	ReviewStatus       string   `json:"review_status"`
}

type resultSummary struct {
	PaperID               uint          `json:"paper_id"`
	Revision              uint          `json:"revision"`
	Title                 string        `json:"title"`
	DOI                   string        `json:"doi"`
	Journal               string        `json:"journal"`
	Year                  *int          `json:"year"`
	MatchedStates         int64         `json:"matched_states"`
	StateID               uint64        `json:"state_id,omitempty"`
	StateKey              string        `json:"state_key,omitempty"`
	Material              string        `json:"material,omitempty"`
	MaterialName          *string       `json:"material_name,omitempty"`
	PressureGPa           *float64      `json:"pressure_gpa"`
	SpaceGroup            *string       `json:"space_group"`
	SpaceGroupNumber      *int          `json:"space_group_number"`
	StructureOptimization string        `json:"structure_optimization,omitempty"`
	Structures            []resultModel `json:"structures,omitempty" gorm:"-"`
}
type resultModel struct {
	ID       string `json:"id"`
	StateKey string `json:"-"`
	PaperID  uint   `json:"-"`
}

// 结果主体是材料状态；物性只用EXISTS约束，避免多条Tc复制状态。
func resultCandidates(db *gorm.DB, b searchResultsRequest, keys []string, structural bool) *gorm.DB {
	key, pressure, material := "cs.system_key", "ms.pressure_value_gpa", "COALESCE(ms.material_name, sc.chemical_formula)"
	var q *gorm.DB
	if structural {
		key, pressure, material = "r.system_key", "r.pressure_gpa", "r.material"
		q = db.Table("paper_structural_records AS r").Joins("JOIN papers AS p ON p.id=r.paper_id AND p.content_revision=r.paper_revision").Where("r.kind='model' AND r.retention='retained'")
	} else {
		q = db.Table("material_states AS ms").Joins("JOIN papers AS p ON p.id=ms.paper_id AND p.content_revision=ms.paper_revision").Joins("LEFT JOIN superconductors AS sc ON sc.id=ms.superconductor_id").Joins("LEFT JOIN chemical_systems AS cs ON cs.id=sc.chemical_system_id")
	}
	q = q.Where("p.review_status='approved' AND p.approved_revision=p.content_revision")
	if len(b.Elements) > 0 || b.Formula != "" {
		q = q.Where(key+" IN ?", keys)
	}
	if b.ReviewStatus != "" && b.ReviewStatus != "approved" {
		q = q.Where("1=0")
	}
	if b.Keyword != "" {
		like := "%" + b.Keyword + "%"
		q = q.Where("("+material+" LIKE ? OR p.title LIKE ? OR p.doi LIKE ? OR p.journal LIKE ?)", like, like, like, like)
	}
	if b.PressureMin != nil {
		q = q.Where(pressure+">=?", *b.PressureMin)
	}
	if b.PressureMax != nil {
		q = q.Where(pressure+"<=?", *b.PressureMax)
	}
	if b.YearMin != nil {
		q = q.Where("p.year>=?", *b.YearMin)
	}
	if b.YearMax != nil {
		q = q.Where("p.year<=?", *b.YearMax)
	}
	if b.SuperconductorType != "" {
		q = q.Where("EXISTS (SELECT 1 FROM paper_material_families pmf JOIN material_families mf ON mf.id=pmf.material_family_id WHERE pmf.paper_id=p.id AND pmf.paper_revision=p.content_revision AND mf.code=?)", b.SuperconductorType)
	}
	if !structural && (b.TcMin != nil || b.TcMax != nil || b.ChartOnly) {
		tc := db.Table("property_records AS pr").Select("1").Where("pr.material_state_id=ms.id AND pr.paper_id=ms.paper_id AND pr.paper_revision=ms.paper_revision AND pr.property_code='tc'")
		value := "COALESCE(pr.value_number,(pr.value_min+pr.value_max)/2)"
		if b.TcMin != nil {
			tc = tc.Where(value+">=?", *b.TcMin)
		}
		if b.TcMax != nil {
			tc = tc.Where(value+"<=?", *b.TcMax)
		}
		if b.ChartOnly {
			tc = tc.Where("pr.is_representative=?", true)
		}
		q = q.Where("EXISTS (?)", tc)
	}
	return q
}

func searchResultKeys(db *gorm.DB, b searchResultsRequest) ([]string, error) {
	selected := stringSet(b.Elements)
	if b.Mode == "formula_search" {
		selected = stringSet(strings.Split(buildFormulaSystemKey(b.Formula), "-"))
	}
	var keys []string
	if err := db.Raw("SELECT system_key FROM chemical_systems UNION SELECT system_key FROM paper_structural_records").Scan(&keys).Error; err != nil {
		return nil, err
	}
	matched := []string{}
	for _, key := range keys {
		set := stringSet(strings.Split(key, "-"))
		ok := false
		switch b.Mode {
		case "elements_exact_search", "formula_search":
			ok = stringSetEqual(set, selected)
		case "elements_contained_search":
			ok = isSubset(selected, set)
		default:
			ok = isSubset(set, selected)
		}
		if ok {
			matched = append(matched, key)
		}
	}
	sort.Strings(matched)
	return matched, nil
}

func SearchResults(c *gin.Context) {
	var b searchResultsRequest
	if c.ShouldBindJSON(&b) != nil || b.Offset < 0 || b.Offset > 100000 || b.Limit < 0 || b.Limit > 100 || len(b.Elements) > 118 {
		c.JSON(400, gin.H{"error": "检索参数无效"})
		return
	}
	if b.View != "states" {
		b.View = "papers"
	}
	if b.Limit == 0 {
		b.Limit = 20
	}
	if b.Mode == "" {
		b.Mode = "elements_combination_search"
	}
	if b.Mode != "formula_search" && b.Mode != "elements_exact_search" && b.Mode != "elements_combination_search" && b.Mode != "elements_contained_search" {
		c.JSON(400, gin.H{"error": "检索模式无效"})
		return
	}
	symbols := stringSet(strings.Fields("H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og"))
	elements := b.Elements
	if b.Mode == "formula_search" {
		elements = strings.Split(buildFormulaSystemKey(b.Formula), "-")
	}
	for _, el := range elements {
		if !symbols[el] {
			c.JSON(400, gin.H{"error": "元素或化学式无效"})
			return
		}
	}
	if (b.PressureMin != nil && b.PressureMax != nil && *b.PressureMin > *b.PressureMax) || (b.TcMin != nil && b.TcMax != nil && *b.TcMin > *b.TcMax) || (b.YearMin != nil && b.YearMax != nil && *b.YearMin > *b.YearMax) {
		c.JSON(400, gin.H{"error": "筛选上下限无效"})
		return
	}
	db := database.DB.WithContext(c.Request.Context())
	keys, err := searchResultKeys(db, b)
	if err != nil {
		searchResultError(c, err)
		return
	}
	states := func() *gorm.DB { return resultCandidates(db, b, keys, false) }
	records := func() *gorm.DB { return resultCandidates(db, b, keys, true) }
	var stateTotal, paperTotal int64
	if err = states().Count(&stateTotal).Error; err != nil {
		searchResultError(c, err)
		return
	}
	papers := func() *gorm.DB {
		return db.Table("papers AS p").Where("p.id IN (?) OR p.id IN (?)", states().Select("ms.paper_id"), records().Select("r.paper_id"))
	}
	if err = papers().Count(&paperTotal).Error; err != nil {
		searchResultError(c, err)
		return
	}
	fields := "p.id AS paper_id,p.content_revision AS revision,p.title,p.doi,p.journal,p.year"
	items := []resultSummary{}
	total := paperTotal
	if b.View == "states" {
		total = stateTotal
		err = states().Select(fields + ",ms.id AS state_id,ms.state_key,sc.chemical_formula AS material,ms.material_name,ms.pressure_value_gpa AS pressure_g_pa,ms.reported_space_group_symbol AS space_group,ms.reported_space_group_number AS space_group_number,ms.structure_optimization").Order("p.year DESC,p.id,ms.pressure_value_gpa IS NULL,ms.pressure_value_gpa,ms.structure_optimization,ms.state_key,ms.id").Limit(b.Limit).Offset(b.Offset).Scan(&items).Error
	} else {
		matched := states().Select("ms.paper_id,COUNT(*) AS matched_states").Group("ms.paper_id")
		err = papers().Joins("LEFT JOIN (?) AS matched ON matched.paper_id=p.id", matched).Select(fields + ",COALESCE(matched.matched_states,0) AS matched_states").Order("p.year DESC,p.id").Limit(b.Limit).Offset(b.Offset).Scan(&items).Error
	}
	if err != nil {
		searchResultError(c, err)
		return
	}
	if b.View == "states" && len(items) > 0 {
		paperIDs := []uint{}
		for _, item := range items {
			paperIDs = append(paperIDs, item.PaperID)
		}
		models := []resultModel{}
		err = records().Where("r.paper_id IN ?", paperIDs).Select("r.id,r.paper_id,r.state_key").Scan(&models).Error
		if err != nil {
			searchResultError(c, err)
			return
		}
		for i := range items {
			for _, m := range models {
				if m.PaperID == items[i].PaperID && m.StateKey == items[i].StateKey {
					items[i].Structures = append(items[i].Structures, m)
				}
			}
		}
	}
	c.Header("Cache-Control", "no-store")
	c.JSON(http.StatusOK, gin.H{"view": b.View, "items": items, "total": total, "papers_total": paperTotal, "states_total": stateTotal, "limit": b.Limit, "offset": b.Offset})
}
func searchResultError(c *gin.Context, err error) {
	c.Error(fmt.Errorf("search results: %w", err))
	c.JSON(503, gin.H{"error": "检索资料暂不可读取，请重试"})
}
