package handlers

import (
	"encoding/json"
	"fmt"
	"github.com/gin-gonic/gin"
	"gorm.io/driver/mysql"
	"gorm.io/gorm"
	"net/http/httptest"
	"os"
	"scwiki/server/database"
	"scwiki/server/middleware"
	"scwiki/server/models"
	"strings"
	"testing"
)

func resultFixture(t *testing.T, db *gorm.DB) *gin.Engine {
	t.Helper()
	database.DB = db
	ddl := []string{
		"CREATE TABLE papers (id INTEGER PRIMARY KEY, content_revision INTEGER, approved_revision INTEGER, review_status VARCHAR(20), title VARCHAR(100), doi VARCHAR(100), journal VARCHAR(100), year INTEGER)",
		"CREATE TABLE chemical_systems (id INTEGER PRIMARY KEY, system_key VARCHAR(100), paper_id INTEGER, paper_revision INTEGER)",
		"CREATE TABLE superconductors (id INTEGER PRIMARY KEY, chemical_system_id INTEGER, chemical_formula VARCHAR(100))",
		"CREATE TABLE material_states (id INTEGER PRIMARY KEY, paper_id INTEGER, paper_revision INTEGER, state_key VARCHAR(100), superconductor_id INTEGER, material_name VARCHAR(100), pressure_value_gpa REAL, reported_space_group_symbol VARCHAR(100), reported_space_group_number INTEGER, structure_optimization VARCHAR(32))",
		"CREATE TABLE paper_structural_records (id VARCHAR(32) PRIMARY KEY, paper_id INTEGER, paper_revision INTEGER, record_key VARCHAR(100), kind VARCHAR(16), material VARCHAR(100), system_key VARCHAR(100), pressure_gpa REAL, state_key VARCHAR(100), retention VARCHAR(20))",
		"CREATE TABLE property_records (id INTEGER PRIMARY KEY, material_state_id INTEGER, paper_id INTEGER, paper_revision INTEGER, property_code VARCHAR(100),value_number REAL,value_min REAL,value_max REAL,is_representative BOOLEAN)",
		"CREATE TABLE material_families (id INTEGER PRIMARY KEY,code VARCHAR(64),normalized_name VARCHAR(160))",
		"CREATE TABLE material_family_aliases (material_family_id INTEGER,normalized_alias VARCHAR(160))",
		"CREATE TABLE paper_material_families (paper_id INTEGER,paper_revision INTEGER,material_family_id INTEGER)",
	}
	for _, sql := range ddl {
		if err := db.Exec(sql).Error; err != nil {
			t.Fatal(err)
		}
	}
	rows := []string{
		"INSERT INTO papers VALUES (271,1,1,'approved','来源论文','10.1/example','PNAS',2024),(272,1,1,'approved','独立模型来源','10.1/model','PNAS',2023),(273,2,1,'approved','旧版本','10.1/old','PNAS',2025),(274,1,NULL,'pending','待审','10.1/pending','PNAS',2025)",
		"INSERT INTO chemical_systems (id,system_key) VALUES (1,'H-La-Sc'),(2,'La-Sc')",
		"INSERT INTO superconductors VALUES (1,1,'LaSc2H24'),(2,2,'LaSc2')",
		"INSERT INTO material_families VALUES (1,'hydrogen_based','氢基超导体'),(2,'custom_test','自建家族')",
		"INSERT INTO material_family_aliases VALUES (1,'hydride'),(1,'hydrogen based')",
		"INSERT INTO paper_material_families VALUES (271,1,1)",
		"INSERT INTO paper_structural_records VALUES ('model1',271,1,'m1','model','LaSc2H24','H-La-Sc',300,'s6','retained'),('independent',272,1,'i1','model','LaSc2','La-Sc',300,NULL,'retained'),('excluded',272,1,'i2','model','LaSc2H24','H-La-Sc',150,NULL,'excluded')",
	}
	for _, sql := range rows {
		if err := db.Exec(sql).Error; err != nil {
			t.Fatal(err)
		}
	}
	pressures := []int{150, 167, 200, 250, 290, 300, 300, 350}
	for i, p := range pressures {
		opt := "sscha"
		if i == 4 || i == 5 || i == 7 {
			opt = "classical_static"
		}
		if err := db.Exec("INSERT INTO material_states VALUES (?,271,1,?,1,NULL,?,'P6/mmm',191,?)", i+1, fmt.Sprintf("s%d", i+1), p, opt).Error; err != nil {
			t.Fatal(err)
		}
	}
	for i := 1; i <= 12; i++ {
		db.Exec("INSERT INTO property_records VALUES (?,?,271,1,'tc',300,NULL,NULL,1)", i, 1+(i%7))
	} // s8 deliberately has no Tc
	db.Exec("INSERT INTO material_states VALUES (100,273,1,'old',1,NULL,300,'P6/mmm',191,'sscha'),(101,274,1,'pending',1,NULL,300,'P6/mmm',191,'sscha')")
	// 第二个体系提供真实多页及同论文跨状态条件的反例。
	db.Exec("INSERT INTO papers VALUES (275,1,1,'approved','多页论文','10.1/pages','PNAS',2022)")
	db.Exec("INSERT INTO chemical_systems (id,system_key) VALUES (3,'Fe'),(4,'O')")
	db.Exec("INSERT INTO superconductors VALUES (3,3,'Fe'),(4,4,'O')")
	for i := 0; i < 41; i++ {
		db.Exec("INSERT INTO material_states VALUES (?,275,1,?,3,NULL,?,'Im-3m',229,'classical_static')", 200+i, fmt.Sprintf("fe-%03d", i), i+1)
	}
	db.Exec("INSERT INTO material_states VALUES (300,275,1,'oxygen',4,NULL,5000,'C2/m',12,'unknown')")
	gin.SetMode(gin.TestMode)
	r := gin.New()
	r.POST("/results", SearchResults)
	return r
}
func callResults(t *testing.T, r *gin.Engine, body string) map[string]any {
	t.Helper()
	w := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/results", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	r.ServeHTTP(w, req)
	if w.Code != 200 {
		t.Fatalf("%d %s", w.Code, w.Body.String())
	}
	v := map[string]any{}
	if err := json.Unmarshal(w.Body.Bytes(), &v); err != nil {
		t.Fatal(err)
	}
	return v
}
func checkSearchResults(t *testing.T, r *gin.Engine) {
	b := `"elements":["H","La","Sc"],"mode":"elements_exact_search"`
	v := callResults(t, r, "{"+b+"}")
	if v["total"] != float64(1) || v["states_total"] != float64(8) {
		t.Fatal(v)
	}
	v = callResults(t, r, "{"+b+`,"view":"states","limit":3,"offset":3}`)
	if len(v["items"].([]any)) != 3 || v["total"] != float64(8) {
		t.Fatal(v)
	}
	v = callResults(t, r, "{"+b+`,"view":"states","pressure_min":300,"pressure_max":300}`)
	items := v["items"].([]any)
	if len(items) != 2 {
		t.Fatal(v)
	}
	if items[0].(map[string]any)["structure_optimization"] == items[1].(map[string]any)["structure_optimization"] {
		t.Fatal(items)
	}
	if items[0].(map[string]any)["pressure_gpa"] != float64(300) {
		t.Fatal(items)
	}
	v = callResults(t, r, "{"+b+`,"chart_only":true}`)
	if v["states_total"] != float64(7) {
		t.Fatal(v)
	}
	v = callResults(t, r, `{"elements":["La","Sc"],"mode":"elements_exact_search"}`)
	if v["papers_total"] != float64(1) || v["states_total"] != float64(0) {
		t.Fatal(v)
	}
	v = callResults(t, r, `{"elements":["La","Sc"],"mode":"elements_contained_search","limit":1}`)
	if v["papers_total"] != float64(2) || v["states_total"] != float64(8) || len(v["items"].([]any)) != 1 {
		t.Fatal(v)
	}
	v = callResults(t, r, "{"+b+`,"view":"states","superconductor_type":"hydride"}`)
	if v["states_total"] != float64(8) {
		t.Fatal(v)
	}
	v = callResults(t, r, `{"elements":["Fe"],"mode":"elements_exact_search","view":"states","offset":20,"limit":20}`)
	if v["total"] != float64(41) || len(v["items"].([]any)) != 20 {
		t.Fatal(v)
	}
	v = callResults(t, r, `{"elements":["Fe"],"mode":"elements_exact_search","pressure_min":500}`)
	if v["total"] != float64(0) {
		t.Fatal("cross-state pressure match", v)
	}
	v = callResults(t, r, "{"+b+`,"review_status":"pending"}`)
	if v["states_total"] != float64(8) {
		t.Fatal(v)
	}
}
func TestSearchResultsUnits(t *testing.T) {
	checkSearchResults(t, resultFixture(t, governanceTestDB(t)))
}
func TestSearchResultsMySQL(t *testing.T) {
	dsn := os.Getenv("SEARCH_RESULTS_TEST_DSN")
	if dsn == "" {
		t.Skip("requires isolated SEARCH_RESULTS_TEST_DSN")
	}
	if !strings.Contains(dsn, "/scwiki_issue178_test_") {
		t.Fatal("refusing non-test database")
	}
	db, err := gorm.Open(mysql.Open(dsn), &gorm.Config{})
	if err != nil {
		t.Fatal(err)
	}
	checkSearchResults(t, resultFixture(t, db))
	if err := db.AutoMigrate(&models.User{}); err != nil {
		t.Fatal(err)
	}
	checkSearchFilterRoleScope(t, db)
}

// 标准目录值及真实鉴权覆盖，不把旧别名误建成正式 code。
func TestSearchFilterCatalogIdentity(t *testing.T) {
	db := governanceTestDB(t)
	r := resultFixture(t, db)
	for _, filter := range []string{`"material_family_id":1`, `"superconductor_type":"hydride"`, `"superconductor_type":"hydrogen_based"`} {
		v := callResults(t, r, `{"elements":["H","La","Sc"],`+filter+`}`)
		if v["states_total"] != float64(8) {
			t.Fatalf("%s: %v", filter, v)
		}
	}
	for _, filter := range []string{`"material_family_id":2`, `"superconductor_type":"missing"`} {
		v := callResults(t, r, `{`+filter+`}`)
		if v["total"] != float64(0) {
			t.Fatal(filter, v)
		}
	}
}
func TestSearchFilterCustomFamily(t *testing.T) {
	db := governanceTestDB(t)
	r := resultFixture(t, db)
	db.Exec("INSERT INTO paper_material_families VALUES (275,1,2)")
	v := callResults(t, r, `{"elements":["Fe"],"mode":"elements_exact_search","material_family_id":2,"view":"states","limit":1,"offset":20}`)
	if v["states_total"] != float64(41) || len(v["items"].([]any)) != 1 {
		t.Fatal(v)
	}
}
func TestSearchFilterRoleScope(t *testing.T) {
	db := governanceTestDB(t)
	resultFixture(t, db)
	checkSearchFilterRoleScope(t, db)
}
func checkSearchFilterRoleScope(t *testing.T, db *gorm.DB) {
	db.Exec("INSERT INTO papers VALUES (276,1,NULL,'rejected','拒绝','10.1/rejected','PNAS',2025)")
	db.Exec("INSERT INTO material_states VALUES (102,273,2,'current',1,NULL,200,'P6/mmm',191,'sscha'),(103,276,1,'rejected',1,NULL,200,'P6/mmm',191,'sscha')")
	db.Exec("INSERT INTO paper_structural_records VALUES ('pending-model',274,1,'pm','model','LaSc2','La-Sc',200,NULL,'retained'),('rejected-model',276,1,'rm','model','LaSc2','La-Sc',200,NULL,'retained')")
	middleware.InitJWT("search-filter-test-only")
	r := gin.New()
	r.POST("/results", middleware.OptionalAuth, SearchResults)
	for _, role := range []string{"anonymous", "user", "admin", "superadmin", "unapproved"} {
		token := ""
		privileged := role == "admin" || role == "superadmin"
		if role != "anonymous" {
			actualRole := role
			if role == "unapproved" {
				actualRole = "admin"
			}
			u := createGovernanceUser(t, db, role, actualRole, "active")
			if role == "unapproved" {
				db.Model(&u).Update("is_approved", false)
				u.IsApproved = false
			}
			token, _ = middleware.GenerateTokenForUser(u)
		}
		for _, status := range []string{"", "approved", "pending", "rejected"} {
			body := `{"elements":["H","La","Sc"],"mode":"elements_exact_search","view":"states","review_status":"` + status + `"}`
			req := httptest.NewRequest("POST", "/results", strings.NewReader(body))
			req.Header.Set("Content-Type", "application/json")
			if token != "" {
				req.Header.Set("Authorization", "Bearer "+token)
			}
			w := httptest.NewRecorder()
			r.ServeHTTP(w, req)
			var v map[string]any
			json.Unmarshal(w.Body.Bytes(), &v)
			want := float64(8)
			if privileged {
				switch status {
				case "":
					want = 11
				case "approved":
					want = 9
				default:
					want = 1
				}
			}
			if w.Code != 200 || v["states_total"] != want {
				t.Fatalf("%s/%s: %d %s", role, status, w.Code, w.Body.String())
			}
			papers := float64(1)
			if privileged && status == "" {
				papers = 4
			}
			if privileged && status == "approved" {
				papers = 2
			}
			if v["papers_total"] != papers {
				t.Fatal(role, status, v)
			}
			modelBody := `{"elements":["La","Sc"],"mode":"elements_exact_search","review_status":"` + status + `","limit":1}`
			modelReq := httptest.NewRequest("POST", "/results", strings.NewReader(modelBody))
			modelReq.Header.Set("Content-Type", "application/json")
			if token != "" {
				modelReq.Header.Set("Authorization", "Bearer "+token)
			}
			modelW := httptest.NewRecorder()
			r.ServeHTTP(modelW, modelReq)
			var mv map[string]any
			json.Unmarshal(modelW.Body.Bytes(), &mv)
			modelWant := float64(1)
			if privileged && status == "" {
				modelWant = 3
			}
			if modelW.Code != 200 || mv["papers_total"] != modelWant || len(mv["items"].([]any)) != 1 {
				t.Fatal(role, status, mv)
			}
			if privileged && status == "" {
				for _, item := range v["items"].([]any) {
					if item.(map[string]any)["state_id"] == float64(100) {
						t.Fatal("旧版本泄漏", v)
					}
				}
			}
		}
	}
}
