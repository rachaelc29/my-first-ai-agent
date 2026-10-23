# 房产短视频生成与发布 SOP｜AI 机读执行版 V2.0

> **Google Doc 为唯一规则真源**：[原始视频 SOP](https://docs.google.com/document/d/1xLYEXPDyW-guNhr331zMjp8CgA_lQOT0YySw7rWc9XI/edit)。
> 本文件为 2026-10-23 获取的只读快照，用于 GitHub 内 AI 查找及在无法访问 Google Docs 时核对；两者不一致时以 Google Doc 最新版为准。严禁只修改此镜像而不核对原文。

---

房产短视频生成与发布 SOP｜AI 机读执行版 V2.0
适用范围：2026 图文排期 → 2026-短视频排期 → Gemini 自主制片 → Google Drive → Make 同步发布 Facebook / Instagram / Threads。最后更新：2026-10-23。
0｜AI 快速路由索引（先看本节，不必每次通读全文）
收到 POST-XXX-TW / 要将帖子转视频 → 执行模块 1、2；收到 VID-XXX-TW / 要制作视频 → 执行模块 2、3、4；收到“换封面” → 执行模块 3.2；收到“审核/修改成片” → 执行模块 4；收到“发布/回填” → 执行模块 5；遇到异常 → 模块 6；任务完成前统一执行模块 7 检查。
一条任务主线：按 Post_ID 读图文来源 D 列 → 转视频口播并写入短视频表 D/E → 素材/封面 → Gemini 自主制作真实动态镜头（3–5 秒/镜头）→ 台湾女声+繁中字幕+轻音乐 → 入库 J 列 → 人工通过后 approved → Make 同步发布三平台 → published。
最高优先级：不触碰个人行动中枢；不新增或重排短视频排期字段；不限定 Gemini 使用哪一种生成模型或软件；视频不得仅是 PPT 式静态图轮播；不凭空捏造房产事实；未发布不可写 published。
1｜事实来源、表格入口与字段字典
原表：《FB社媒贴文自动发布排期表》Google Sheets，ID 1fxRV7mhyvnYEPAEow6WFMMvY7zlG8ctyIY-KdmUXwsc。图文来源 Tab“2026”：A Post_ID；B Project_Name；C Post_Theme；D Post_Content【主文案】；I Drive_Image_Id【原图补充】；J Cover_Thumbnail【封面优先】；K INS_Threads_Content【语感辅助】。原帖 D 列和建案资料为事实输入，K 列不代替 D 列。
输出 Tab“2026-短视频排期”：A Video_ID；B Post_ID；C Project_Name；D Hook_Title；E Voiceover_Script；F Cover_Image_Id；G Media_Folder_Link；H Media_Asset_Ids；I Status；J Video_Drive_Link；K Published_Time；L FB_Post_URL。原有列和数据不改变，不增设三平台分别状态列。
单条来源匹配：按 B 列 Post_ID 连接图文 A 列，不以行号或文件名猜测；同一 Post_ID 可衍生多个 VID，但须使用新的唯一 Video_ID；重复执行时先定位已有 VID，防止重复创建。Project_Name 与文案或素材指向不一致时先暂停当前任务，要求核实。
继承《房产社媒文案生成规则 SOP》：项目核心卖点与《房产项目资料库》是事实依据；台湾／香港市场繁体用语（預售屋、建案、投報率、自備款、公設、交屋、置產）；拒绝虚构价格、面积、租金、交付、距离、景观保证；拒绝“重新定义”“尽享奢华”、机械互动和明显 AI 广告腔。不同事实冲突时先核验，不自行补全。
2｜脚本生成（POST → VID）
2.1 按指定 POST-XXX-TW 检索图文 Tab“2026”对应行，读取 D Post_Content、B 项目、C 主题及 J 封面，并按项目名称核对资料库。
2.2 只选一个清晰的核心卖点，先提供 3 秒 Hook，再改写成适合 20–40 秒的台湾日常口语脚本；时长取决于文案内容与自然语速，不强制字数或固定 30 秒。真实信息比夸张吸睛更重要。开头明确主题，结尾给项目名和低摩擦私讯 CTA。
2.3 写回现有短视频 Tab：A 唯一 VID、B Post_ID、C Project_Name、D Hook_Title、E Voiceover_Script。不要因“脚本生成”就标记 approved；approved 专指成片已经由用户审核同意、等待 Make 发布。写入前检查该 VID 是否已存在或已有人为修改。
3｜素材、封面、视频镜头
3.1 素材：优先对应项目 Google Drive 官方图片/原视频、PDF 内高清原图、开发商授权资料；可补充合法商用的街区实景或 AI 辅助素材。PDF 优先无白边提取原图。严禁拿 A 项目图片冒充 B 项目，或把生成想象画面当作实际设施。记录所用素材在 G、H 原有字段。
3.2 封面：先检查原图文“2026” Tab J Cover_Thumbnail 图片及其原始文件。符合 9:16、清晰且关键信息不被遮挡时优先沿用；若比例不合，优先安全裁切/重新排版；无法有效裁切时重新生成 9:16 繁体封面，保存 Google Drive“媒体临时加字图库”（文件夹 ID 13nQ44D9pFllSwhXwPcESnrWsqZevxr8E），以 VID 命名，并将最终文件 ID 写入视频表 F 列。不要把成品封面放进原始项目素材库。
3.3 镜头：每个镜头建议 3–5 秒，画面内容与当句口播对应；建筑外观、入口、室内、公设、周边街区根据主题分别设计自然运镜。优先真实动态视频或图生视频；严禁全片只靠简单缩放、平移、淡入淡出冒充动态影像。允许 Gemini 自主选择工具、模型和制作流程，不预设具体厂商。
3.4 房地产真实性红线：AI 视频不应改变建筑主体、户型布局、门窗、外立面、公共设施及道路位置；避免穿墙、扭曲、不可能视角和虚构景观。无法保证准确的镜头退回使用真实素材或清楚标识的示意镜头。
4｜配音、字幕、合成与人工验收
4.1 视频规格：9:16、优先 1080×1920 MP4；20–40 秒为参考范围。台湾女声自然亲切、英文地名发音合理；繁体中文字幕逐句同步且避开平台按钮；背景轻音乐清淡，不能盖过人声，必须具备商业使用许可。
4.2 成片验收：不是 PPT；每 3–5 秒镜头有效切换、节奏自然；画面贴合脚本，住宅事实无误；没有白边、黑屏、断句、错别字、口型/声音异常；开头吸睛、结尾项目及 CTA 清楚。发现问题优先局部修订，不重复消耗全部镜头。
4.3 成片存 Google Drive“项目短视频”（文件夹 ID 1C2jBW2fe3VjWuRRvRji0P9zpaa6E_F0s），文件名 Video_ID_项目名_主题.mp4；把真实可访问的链接填入视频表 J。成片先给用户预览，同意后才将视频表 I 写 approved。
5｜Make 发布与最简状态
I Status 只有两个业务发布状态：approved＝用户审核成片通过，等待发布；published＝Make 已完成 Facebook、Instagram、Threads 一键联合发布。尚未审核完成时 I 保持空白，不使用额外状态。
Make 只处理 I=approved 且 J 视频链接非空、媒体可供发布模块访问的任务。上传至 Google Drive 并不等于 Meta 能直接匿名读取，必须按 Make 使用的授权/媒体入口实测可访问性。发布前防重：检查同 VID 是否已经发出；平台任一未成功时不可标记 published，异常由 Make 日志处理，不新建三个平台状态字段。
统一发布完成后写 I=published、K=Published_Time、L=FB_Post_URL。现表只有 FB 链接字段，不强行新增 IG/Threads 链接列；需要排障时到 Make 执行历史查看。不要声称未验证的多平台自动同步已部署。
6｜异常处理（仅按需读取）
无 POST 或关联错误：不生成任务；无可用项目图：可使用合规示意素材，但不能冒充建案实拍；J 封面不合 9:16：安全裁切或重新生成入临时库；生成模型不可用/费用过高：保留脚本与素材，报告阻断，不能降级成 PPT 假装达到要求；声音不自然/版权不明：更换资源；Make 部分失败：保持 approved，不重复发送已成功的平台，由 Make 的失败恢复逻辑处理；不修改个人行动中枢。
7｜交付前检查清单（Pre-flight Assertions）
□ Post_ID、Video_ID、Project_Name 一致，原帖 D 列内容被正确引用；□ 视频排期 D/E 写对、现有字段未损坏；□ 使用原帖 J 列封面或有理由重做并保存至媒体临时加字图库；□ 图片与镜头贴合脚本，3–5 秒、实质动态而非 PPT；□ 建筑与数值不编造；□ 台湾女声、繁体字幕、轻音乐合格；□ 视频符合 9:16、无白边且可播放；□ J 链接可访问、用户审核后才 approved；□ Make 三平台完成后才 published、K/L 回填真实结果；□ 仅更新本视频相关对象，无操作个人行动中枢。
8｜最短执行口令（供 AI Agent 调用）
“按照《房产短视频生成与发布 SOP》处理 POST-XXX-TW：从‘2026’的 D 列读取原文，生成并写入短视频排期 D/E，按 J 列优先处理 9:16 封面，自动寻找对应项目素材并生成每镜头 3–5 秒的真实动态视频，配台湾女声、繁体字幕和轻音乐。输出 MP4 至‘项目短视频’并回填 J。交给我审核；审核通过设置 approved 后由 Make 一键发布 FB、IG、Threads；发布成功统一标记 published。不得擅改表结构或个人行动中枢。”
9｜关联资源（只作引用，不在此复制维护）
文案规则 Doc：https://docs.google.com/document/d/1KnORN0JIk9tAYJpF46TWowsljf9u1z-9hsf8NOV3chM/edit
排期 Sheet：https://docs.google.com/spreadsheets/d/1fxRV7mhyvnYEPAEow6WFMMvY7zlG8ctyIY-KdmUXwsc/edit
工作日志：https://docs.google.com/document/d/1nkMvs4Qv6w3p7L0-ZPFSN6boZpzP1lGKp5hRKixoOGc/edit
版本约束：此文件为规则真源；Spreadsheet 的“短视频生成SOP”仅为快速路由摘要，避免两份长文独立漂移。文案规则 Doc 管文字风格，本文专管视频流程；如冲突，以更具体的视频安全与字段规则为准。
