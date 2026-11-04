# 验证操作

以下命令从仓库根执行。Python 先用 python3 -m scripts.local_deploy.environment "/Users/mayuan/Codes/SC-Wiki" 定位。

## 自动测试

    DATABASE_URL="sqlite:///:memory:" JWT_SECRET_KEY="isolated-dos-test-secret" /Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python -m pytest backend/tests/test_spectra*.py backend/tests/test_alpha2f_relative.py -q

frontend 目录运行：

    npm run test:upload-ui -- tests/01_decentralized_uploading/spectrum-dos-relative.test.tsx tests/01_decentralized_uploading/spectrum-recalculate.test.tsx tests/01_decentralized_uploading/spectrum-relative.test.tsx tests/01_decentralized_uploading/spectrum-workspace.test.tsx tests/01_decentralized_uploading/property-spectra-navigation.test.tsx
    npm run build

## 隔离正式页面

每次使用新的 /tmp/scwiki-manual-test- 前缀目录，并创建其 browser 子目录。设置 DATABASE_URL 为该目录下 SQLite，SCWIKI_MANUAL_TEST_ROOT 为该目录，FILE_STORAGE_BACKEND=local，FILE_STORAGE_LOCAL_ROOT 为该目录的 files 子目录，JWT_SECRET_KEY 使用测试值。入口会拒绝不在临时目录内的存储根。

    python -m uvicorn backend.tests.dos_relative_server:app --host 127.0.0.1 --port 8194

另一终端在 frontend 启动专用 Vite：

    npm run dev -- --host 127.0.0.1 --port 5175 --strictPort

设 SCWIKI_SPECTRUM_BROWSER_OUT 为上述 browser 目录，从仓库根执行：

    node tests/01_decentralized_uploading/spectrum-dos-relative-production.cjs

预期：模式积分 4/5、预期 3/6、偏差保留；缺 N 时只显示面积/占比；刷新不会累乘；390px 无页面整体溢出。结果见 validation.md。退出后停止两个专用测试进程，不操作现有开发服务。

## TDOS 验收

运行相同后端/前端及浏览器入口，补充检查明确 total 的单谱在两项元素标记均为 false 时仍归一化；元素列留空，实际范围保留。未知单线和元素单分波不能按总谱放行。真实原图隔离校验使用当前 discovery.calibrate 与 engine.extract_panel，随后通过正式重算/导出路由保存和重读；保留失败响应，不写用户草稿或业务库。

真实来源页面复现：把 validation/tdos/source-fixture.json 和 source.png 复制到上述新建的隔离根目录，启动服务时令 SCWIKI_TDOS_SOURCE_FIXTURE 指向复制后的 JSON。浏览器脚本会额外验证 dos-real-source；不用该变量时仍验证合成 TDOS。夹具只包含已保存人工描线及由本轮新读图确认的身份，不是本轮重新描线成功的证据。

## 纵轴刻度优先验收

沿用validation/tdos/source-fixture.json中的固定人工描线与当前标定：应按刻度显示6.308648445665745任意单位·THz，界面约6.30865；确认标准TDOS、N=7时系数约3.32876370919475、总模式21。没有可用纵轴刻度的独立夹具仍应显示像素·THz。分别检查缺N/未知身份时独立积分仍显示，绝对密度原值不被归一化替代，以及CSV/重读单位一致。当前v5已实现该显示；正式浏览器同时验证已确认TDOS，以及同一描线但身份未知/无N时独立积分仍可见。证据位于validation/axis-calibration/。

## 五列表格验收

沿用隔离浏览器入口和真实来源夹具，检查表头恰为元素／TDOS、积分范围、积分值、面积占比、原子数占比；单位置于列标题括号内，数据格仅数值、表内没有S15内部ID。只有CaH6总谱时仍应显示Ca、H两行，原子数比14.29%/85.71%，三项未计算值为—。未知投影显示待确认，同时保留元素清单；旧v5没有composition时已有可信结构计数仍可支持显示。证据见validation/five-column-table/。

表头示例为积分范围（THz）、积分值（任意单位·THz · 纵轴刻度），数据格不得重复单位。像素及其他实际积分单位同样使用括号表头；混合单位分表。现有frequency_interval_thz始终按THz显示，不能直接重标原图cm-1/meV。
