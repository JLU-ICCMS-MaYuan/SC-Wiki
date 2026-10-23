const portraits = import.meta.glob('./portraits/original/*.jpg', { eager: true, query: '?url', import: 'default' }) as Record<string, string>
const portrait = (name: string) => portraits[`./portraits/original/${name}`]

export type NobelSource = {
  label: string
  url: string
  supports: string
}

export type NobelLaureate = {
  id: string
  name: string
  englishName: string
  years: string
  awardYear: number
  prizeShare: string
  identity: string
  identityNote?: string
  achievement: string
  career: string
  awardReason: string
  superconductivityLink: string
  image: string
  sources: NobelSource[]
}

const prize = (year: number) => `https://www.nobelprize.org/prizes/physics/${year}/${year === 1913 ? "summary" : "press-release"}/`
const person = (year: number, slug: string, page: 'facts' | 'biographical' = 'biographical') => `https://www.nobelprize.org/prizes/physics/${year}/${slug}/${page}/`

export const laureates: NobelLaureate[] = [
  {
    id: 'onnes', name: '海克·卡末林·昂内斯', englishName: 'Heike Kamerlingh Onnes', years: '1853–1926', awardYear: 1913, prizeShare: '1/1',
    identity: '荷兰 · 莱顿大学低温实验室', achievement: '低温物质性质研究，并实现氦液化；他在液氦实验中发现汞的超导转变。',
    career: '昂内斯在格罗宁根和海德堡学习物理，后来在莱顿大学建立低温研究实验室。他发展了液化气体与低温测量技术，并于 1908 年实现氦液化；1911 年研究汞在极低温下的电阻变化，发现电阻骤降至不可测的现象。',
    awardReason: '诺贝尔奖授奖理由是低温下物质性质研究，尤其包括液氦的制备。超导发现是这项低温研究的重要结果。',
    superconductivityLink: '首位观测到超导转变的科学家，开启了超导实验研究。', image: portrait('heike-onnes.jpg'),
    sources: [
      { label: '诺贝尔奖：昂内斯事实资料', url: person(1913, 'onnes', 'facts'), supports: '生卒年份与官方人物资料' },
      { label: '诺贝尔奖：昂内斯传记', url: person(1913, 'onnes'), supports: '科研经历、低温实验和氦液化' },
      { label: '诺贝尔奖：1913 年物理学奖', url: prize(1913), supports: '官方授奖理由' },
    ],
  },
  {
    id: 'bardeen', name: '约翰·巴丁', englishName: 'John Bardeen', years: '1908–1991', awardYear: 1972, prizeShare: '1/3',
    identity: '美国 · 伊利诺伊大学厄巴纳—香槟分校', achievement: '与 Cooper、Schrieffer 共同建立解释常规超导的微观理论（BCS 理论）。',
    career: '巴丁先后在威斯康星大学、普林斯顿大学和贝尔实验室工作，参与晶体管研究并于 1956 年获得诺贝尔物理学奖。此后他在伊利诺伊大学与 Cooper、Schrieffer 合作，发展超导微观理论，成为唯一两次获得诺贝尔物理学奖的人。',
    awardReason: '1972 年诺奖授予三人“共同提出超导理论，通常称为 BCS 理论”。这是巴丁第二次获物理学奖；本次获奖理由是超导理论。',
    superconductivityLink: 'BCS 理论以电子形成库珀对解释常规超导态。', image: portrait('john-bardeen.jpg'),
    sources: [
      { label: '诺贝尔奖：巴丁事实资料', url: person(1972, 'bardeen', 'facts'), supports: '生卒年份与获奖时任职身份' },
      { label: '诺贝尔奖：巴丁传记', url: person(1972, 'bardeen'), supports: '科研经历及两次获奖背景' },
      { label: '诺贝尔奖：1972 年物理学奖', url: prize(1972), supports: '共同授奖理由' },
      { label: 'Bardeen、Cooper 与 Schrieffer，Physical Review (1957)', url: 'https://doi.org/10.1103/PhysRev.108.1175', supports: 'BCS 理论原始论文' },
    ],
  },
  {
    id: 'cooper', name: '利昂·库珀', englishName: 'Leon Cooper', years: '1930–2024', awardYear: 1972, prizeShare: '1/3',
    identity: '美国 · 布朗大学', achievement: '与 Bardeen、Schrieffer 共同提出 BCS 超导理论；“库珀对”是该理论的核心概念。',
    career: '库珀在哥伦比亚大学接受物理学训练，曾在普林斯顿高等研究院和伊利诺伊大学从事研究，后来长期任职布朗大学。他关于费米面附近电子配对的研究成为 BCS 超导理论的重要组成部分。',
    awardReason: '诺贝尔奖将 1972 年物理学奖共同授予库珀、巴丁和施里弗，以表彰他们提出 BCS 超导理论。',
    superconductivityLink: '库珀对为常规超导理论提供微观配对图像。', image: portrait('leon-cooper.jpg'),
    sources: [
      { label: '诺贝尔奖：库珀事实资料', url: person(1972, 'cooper', 'facts'), supports: '生卒年份与官方人物资料' },
      { label: '诺贝尔奖：库珀传记', url: person(1972, 'cooper'), supports: '科研经历' },
      { label: '诺贝尔奖：1972 年物理学奖', url: prize(1972), supports: '共同授奖理由' },
      { label: 'Bardeen、Cooper 与 Schrieffer，Physical Review (1957)', url: 'https://doi.org/10.1103/PhysRev.108.1175', supports: 'BCS 理论原始论文' },
    ],
  },
  {
    id: 'schrieffer', name: '约翰·施里弗', englishName: 'John Schrieffer', years: '1931–2019', awardYear: 1972, prizeShare: '1/3',
    identity: '美国 · 宾夕法尼亚大学', achievement: '与 Bardeen、Cooper 共同提出 BCS 超导理论，并给出理论的关键数学构造。',
    career: '施里弗在麻省理工学院学习物理，之后进入伊利诺伊大学研究超导问题。他在 1957 年形成 BCS 理论的关键波函数构造，随后任教于芝加哥大学、宾夕法尼亚大学和佛罗里达州立大学。',
    awardReason: '1972 年诺贝尔物理学奖共同授予施里弗、巴丁和库珀，以表彰 BCS 超导理论。',
    superconductivityLink: '施里弗对 BCS 基态波函数的构造使超导微观理论得以完整表达。', image: portrait('john-schrieffer.jpg'),
    sources: [
      { label: '诺贝尔奖：施里弗事实资料', url: person(1972, 'schrieffer', 'facts'), supports: '生卒年份与官方人物资料' },
      { label: '诺贝尔奖：施里弗传记', url: person(1972, 'schrieffer'), supports: '科研经历' },
      { label: '诺贝尔奖：1972 年物理学奖', url: prize(1972), supports: '共同授奖理由' },
      { label: 'Bardeen、Cooper 与 Schrieffer，Physical Review (1957)', url: 'https://doi.org/10.1103/PhysRev.108.1175', supports: 'BCS 理论原始论文' },
    ],
  },
  {
    id: 'esaki', name: '江崎玲于奈', englishName: 'Leo Esaki', years: '1925–', awardYear: 1973, prizeShare: '1/4',
    identity: '日本 · 获奖时任职 IBM 研究实验室（美国）', identityNote: '国家/机构身份按诺奖资料所列的获奖时任职地点说明，不据出生地推定国籍。',
    achievement: '因发现半导体中的电子隧穿现象获奖，并发展隧道二极管；其获奖贡献并非超导研究。',
    career: '江崎在东京大学接受物理学训练，早年在东京通信工业（后为 Sony）从事半导体研究，之后在 IBM Thomas J. Watson 研究中心继续工作。他对重掺杂半导体中隧穿电流的研究促成隧道二极管的发现。',
    awardReason: '1973 年诺贝尔物理学奖的一半由江崎玲于奈和 Ivar Giaever 平分，两人各获全奖的 1/4，分别表彰半导体和超导体中的实验性隧穿发现；另一半授予 Brian Josephson，表彰超电流穿过隧道势垒的理论预言。',
    superconductivityLink: '三人的研究都涉及量子隧穿，但研究对象与具体成果不同：江崎研究半导体，Giaever 研究超导体中的电子隧穿，Josephson 预言超导隧道结中的超电流。江崎因此列入相关隧穿里程碑，不应被写成因超导贡献获奖。', image: portrait('leo-esaki.jpg'),
    sources: [
      { label: '诺贝尔奖：江崎事实资料', url: person(1973, 'esaki', 'facts'), supports: '出生信息与官方人物资料' },
      { label: '诺贝尔奖：江崎传记', url: person(1973, 'esaki'), supports: '科研经历与半导体隧穿研究' },
      { label: '诺贝尔奖：1973 年物理学奖', url: prize(1973), supports: '江崎与 Giaever 的共同授奖理由' },
      { label: 'Esaki，Physical Review (1958)', url: 'https://doi.org/10.1103/PhysRev.109.603', supports: '半导体隧穿原始论文' },
    ],
  },
  {
    id: 'giaever', name: '伊瓦尔·贾埃弗', englishName: 'Ivar Giaever', years: '1929–2025', awardYear: 1973, prizeShare: '1/4',
    identity: '美国 · 通用电气研究实验室', identityNote: '挪威出生；官方传记明确记载其于 1964 年加入美国国籍，早于 1973 年获奖。',
    achievement: '实验验证超导体中的电子隧穿，测得与超导能隙有关的隧穿特征。',
    career: '贾埃弗在挪威学习工程，移居美国后进入通用电气研究实验室。他利用金属薄膜绝缘层结开展低温隧穿实验，观察到超导体能隙的特征，并将隧穿谱用于研究超导态。',
    awardReason: '1973 年诺贝尔物理学奖的一半由贾埃弗和江崎玲于奈平分，两人各获全奖的 1/4。江崎的贡献是半导体隧穿，贾埃弗的贡献是超导体中的电子隧穿；另一半授予约瑟夫森。',
    superconductivityLink: 'Giaever 的超导隧穿实验为能隙测量和隧穿谱学奠定了基础。', image: portrait('ivar-giaever.jpg'),
    sources: [
      { label: '诺贝尔奖：Giaever 事实资料', url: person(1973, 'giaever', 'facts'), supports: '生卒年份与官方人物资料' },
      { label: '诺贝尔奖：Giaever 传记', url: person(1973, 'giaever'), supports: '科研经历与隧穿实验' },
      { label: '诺贝尔奖：1973 年物理学奖', url: prize(1973), supports: '共同授奖理由' },
      { label: 'Giaever，Physical Review Letters (1960)', url: 'https://doi.org/10.1103/PhysRevLett.5.147', supports: '超导隧穿实验原始论文' },
    ],
  },
  {
    id: 'josephson', name: '布赖恩·约瑟夫森', englishName: 'Brian Josephson', years: '1940–', awardYear: 1973, prizeShare: '1/2',
    identity: '英国 · 剑桥大学', achievement: '预言超导隧道结中的库珀对隧穿及其直流、交流效应（约瑟夫森效应）。',
    career: '约瑟夫森在剑桥大学学习并开展理论研究。研究生期间，他分析两个超导体由薄势垒隔开时的量子隧穿，预言即使没有外加电压也能有超导电流，以及电压下的交流效应；随后这些效应得到实验验证。',
    awardReason: '1973 年诺贝尔物理学奖的一半授予约瑟夫森，表彰他对隧道势垒超导电流性质的理论预言。',
    superconductivityLink: '约瑟夫森效应成为超导量子干涉器件、精密电压标准和超导电子学的基础现象。', image: portrait('brian-josephson.jpg'),
    sources: [
      { label: '诺贝尔奖：约瑟夫森事实资料', url: person(1973, 'josephson', 'facts'), supports: '出生信息与官方人物资料' },
      { label: '诺贝尔奖：约瑟夫森传记', url: person(1973, 'josephson'), supports: '科研经历与理论预言' },
      { label: '诺贝尔奖：1973 年物理学奖', url: prize(1973), supports: '个人授奖理由' },
      { label: 'Josephson，Physics Letters (1962)', url: 'https://doi.org/10.1016/0031-9163(62)91369-0', supports: '约瑟夫森效应理论论文' },
    ],
  },
  {
    id: 'bednorz', name: '格奥尔格·贝德诺尔茨', englishName: 'Georg Bednorz', years: '1950–', awardYear: 1987, prizeShare: '1/2',
    identity: '西德（现德国）出生 · 获奖时任职 IBM 苏黎世研究实验室（瑞士）', identityNote: '诺奖事实页注明出生地当时为西德；身份描述另列获奖时研究机构，避免将出生国家误作获奖时国籍。',
    achievement: '发现镧钡铜氧化物陶瓷中的高温超导性。',
    career: '贝德诺尔茨 1968 年在明斯特大学开始学习化学，随后转向晶体学；1977 年到苏黎世联邦理工学院攻读博士。他 1982 年正式加入 IBM，1983 年起与 Alex Müller 寻找高转变温度氧化物，1986 年取得突破。',
    awardReason: '1987 年诺贝尔物理学奖授予贝德诺尔茨和 Müller，以表彰他们发现陶瓷材料中的超导性。',
    superconductivityLink: '铜氧化物高温超导发现开启了新一轮高温超导研究。', image: portrait('georg-bednorz.jpg'),
    sources: [
      { label: '诺贝尔奖：贝德诺尔茨事实资料', url: person(1987, 'bednorz', 'facts'), supports: '出生信息与官方人物资料' },
      { label: '诺贝尔奖：贝德诺尔茨传记', url: person(1987, 'bednorz'), supports: '科研经历与 IBM 合作' },
      { label: '诺贝尔奖：1987 年物理学奖', url: prize(1987), supports: '共同授奖理由' },
      { label: 'Bednorz 与 Müller，Zeitschrift für Physik B (1986)', url: 'https://doi.org/10.1007/BF01303701', supports: '铜氧化物超导发现原始论文' },
    ],
  },
  {
    id: 'mueller', name: '亚历克斯·米勒', englishName: 'Alex Müller', years: '1927–2023', awardYear: 1987, prizeShare: '1/2',
    identity: '瑞士 · 获奖时任职 IBM 苏黎世研究实验室',
    achievement: '与 Bednorz 发现陶瓷氧化物中的高温超导性。',
    career: '米勒在苏黎世联邦理工学院学习物理，后来长期在 IBM 苏黎世研究实验室工作并参与固体物理研究。他与贝德诺尔茨探索氧化物陶瓷的电子性质，合作发现镧钡铜氧体系的高温超导现象。',
    awardReason: '1987 年诺贝尔物理学奖授予米勒和贝德诺尔茨，以表彰他们发现陶瓷材料中的超导性。',
    superconductivityLink: '两人发现的体系在约 35 K 出现超导迹象，推动了铜氧化物高温超导研究；它本身尚未达到液氮温区（约 77 K）。', image: portrait('alex-mueller.jpg'),
    sources: [
      { label: '诺贝尔奖：Müller 事实资料', url: person(1987, 'muller', 'facts'), supports: '生卒年份与官方人物资料' },
      { label: '诺贝尔奖：Müller 传记', url: person(1987, 'muller'), supports: '科研经历与合作背景' },
      { label: '诺贝尔奖：1987 年物理学奖', url: prize(1987), supports: '共同授奖理由' },
      { label: 'Bednorz 与 Müller，Zeitschrift für Physik B (1986)', url: 'https://doi.org/10.1007/BF01303701', supports: '铜氧化物超导发现原始论文' },
    ],
  },
  {
    id: 'abrikosov', name: '阿列克谢·阿布里科索夫', englishName: 'Alexei Abrikosov', years: '1928–2017', awardYear: 2003, prizeShare: '1/3',
    identity: '美国、俄罗斯 · 阿贡国家实验室', identityNote: '2003 年诺奖新闻稿明确列出美国及俄罗斯公民身份；其出生地当时属于苏联。',
    achievement: '发展第二类超导体理论，预言磁通以量子化涡旋形式进入材料。',
    career: '阿布里科索夫在莫斯科国立大学接受理论物理训练，曾在 Landau 理论物理研究所工作，后加入美国阿贡国家实验室。他基于 Ginzburg–Landau 理论描述第二类超导体的混合态，并推导出规则排列的磁通涡旋结构。',
    awardReason: '2003 年诺贝尔物理学奖由阿布里科索夫、Ginzburg 和 Leggett 各获三分之一，表彰其对超导体和超流体理论的开创性贡献。阿布里科索夫的核心工作是第二类超导体理论。',
    superconductivityLink: '第二类超导体涡旋理论解释强磁场下超导态与磁通共存的行为。', image: portrait('alexei-abrikosov.jpg'),
    sources: [
      { label: '诺贝尔奖：阿布里科索夫事实资料', url: person(2003, 'abrikosov', 'facts'), supports: '生卒年份、出生地与官方人物资料' },
      { label: '诺贝尔奖：阿布里科索夫传记', url: person(2003, 'abrikosov'), supports: '科研经历与第二类超导理论' },
      { label: '诺贝尔奖：2003 年物理学奖', url: prize(2003), supports: '共同授奖理由与超导/超流贡献区分' },
    ],
  },
  {
    id: 'ginzburg', name: '维塔利·金兹堡', englishName: 'Vitaly Ginzburg', years: '1916–2009', awardYear: 2003, prizeShare: '1/3',
    identity: '俄罗斯 · 列别捷夫物理研究所（苏联时期开展主要早期工作）',
    achievement: '与 Landau 建立超导现象的唯象理论（Ginzburg–Landau 理论）。',
    career: '金兹堡在莫斯科国立大学学习物理，之后长期在列别捷夫物理研究所工作。他研究电磁波传播、天体物理和凝聚态物理；1950 年与 Landau 提出描述超导相变和宏观序参量的理论框架。',
    awardReason: '2003 年诺贝尔物理学奖由 Ginzburg、Abrikosov 和 Leggett 各获三分之一，表彰其对超导体和超流体理论的开创性贡献。',
    superconductivityLink: 'Ginzburg–Landau 理论以宏观序参量描述超导态，并为第二类超导理论奠定基础。', image: portrait('vitaly-ginzburg.jpg'),
    sources: [
      { label: '诺贝尔奖：Ginzburg 事实资料', url: person(2003, 'ginzburg', 'facts'), supports: '生卒年份与官方人物资料' },
      { label: '诺贝尔奖：Ginzburg 传记', url: person(2003, 'ginzburg'), supports: '科研经历与理论工作' },
      { label: '诺贝尔奖：2003 年物理学奖', url: prize(2003), supports: '共同授奖理由' },
    ],
  },
  {
    id: 'leggett', name: '安东尼·莱格特', englishName: 'Anthony Leggett', years: '1938–2026', awardYear: 2003, prizeShare: '1/3',
    identity: '英国、美国 · 伊利诺伊大学厄巴纳—香槟分校', identityNote: '官方传记记载其 2002 年取得美国国籍并保留英国国籍；2003 年新闻稿明确列出双重国籍。',
    achievement: '解释超流氦-3 的宏观量子性质，特别是配对态与序参量结构。',
    career: '莱格特在牛津大学接受物理学训练，先后在牛津、苏塞克斯大学和伊利诺伊大学从事理论研究。他发展了对超流氦-3 多种配对态的理论理解，并研究宏观量子系统中的对称性与量子相干现象。',
    awardReason: '2003 年诺贝尔物理学奖由莱格特、Abrikosov 和 Ginzburg 各获三分之一。莱格特获奖所表彰的是超流氦-3 理论，不是因超导研究获奖。',
    superconductivityLink: '本展将莱格特列入同一年度超导/超流理论里程碑；明确区分其诺奖所表彰的超流研究与超导贡献。', image: portrait('anthony-leggett.jpg'),
    sources: [
      { label: '诺贝尔奖：莱格特事实资料', url: person(2003, 'leggett', 'facts'), supports: '生卒年份、出生地与官方人物资料' },
      { label: '诺贝尔奖：莱格特传记', url: person(2003, 'leggett'), supports: '科研经历与超流氦-3 理论' },
      { label: '诺贝尔奖：2003 年物理学奖', url: prize(2003), supports: '个人获奖贡献与超流氦-3 理由' },
      { label: 'Leggett，Reviews of Modern Physics (1975)', url: 'https://doi.org/10.1103/RevModPhys.47.331', supports: '超流氦-3 理论综述' },
    ],
  },
]
