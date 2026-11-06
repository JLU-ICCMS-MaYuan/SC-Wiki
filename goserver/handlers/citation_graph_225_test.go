package handlers

import (
	"testing"
)

func TestKG225OverviewRequiresTitleButSearchAndExpansionDoNot(t *testing.T) {
	db := graphTestDB(t)
	for id := uint(1); id <= 4; id++ {
		graphPaper(t, db, id, "Paper", "approved", "conventional")
	}
	for id, value := range map[uint]interface{}{2: "", 3: " \t\n\r　 ", 4: nil} {
		if err := db.Exec("UPDATE papers SET knowledge_graph_title = ? WHERE id = ?", value, id).Error; err != nil {
			t.Fatal(err)
		}
		graphReference(t, db, id, 1, 0)
	}
	body := graphResponse(t, KGOverview, "")
	if len(graphNodesFromResponse(t, body)) != 1 || body["total_nodes"] != float64(1) {
		t.Fatalf("空图谱标题进入概览: %#v", body)
	}
	body = graphResponse(t, KGSearch, "?q=Paper")
	if len(graphNodesFromResponse(t, body)) != 4 {
		t.Fatalf("搜索错误过滤无短标题论文: %#v", body)
	}
	body = graphResponseAt(t, KGPaperNeighbors, "/papers/:paperId/neighbors", "/papers/1/neighbors?direction=downstream")
	if len(graphNodesFromResponse(t, body)) != 3 {
		t.Fatalf("展开错误过滤无短标题论文: %#v", body)
	}
}

func TestKG225ExpansionIncludesCrossEdgesBetweenVisiblePapers(t *testing.T) {
	db := graphTestDB(t)
	for id := uint(1); id <= 4; id++ {
		graphPaper(t, db, id, "Paper", "approved", "conventional")
	}
	graphReference(t, db, 4, 1, 0)
	graphReference(t, db, 4, 2, 1)
	graphReference(t, db, 2, 1, 0)
	graphReference(t, db, 3, 2, 0)
	body := graphResponseAt(t, KGPaperNeighbors, "/papers/:paperId/neighbors",
		"/papers/4/neighbors?direction=upstream&visible_paper_id=3")
	if len(body["edges"].([]interface{})) != 4 {
		t.Fatalf("新增节点与已有节点之间的引用边遗漏: %#v", body)
	}
}
