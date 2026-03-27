import { useState, useEffect, useCallback } from 'react'
import { fetchJSON, subscribeSSE } from './api.js'
import ForceGraph3D from 'react-force-graph-3d'

// ====================================================================
// 主应用
// ====================================================================

export default function App() {
    const [page, setPage] = useState('dashboard')
    const [dashboardData, setDashboardData] = useState(null)
    const [refreshKey, setRefreshKey] = useState(0)
    const [connected, setConnected] = useState(false)

    const loadDashboardData = useCallback(() => {
        fetchJSON('/api/dashboard/summary')
            .then(setDashboardData)
            .catch(() => setDashboardData(null))
    }, [])

    useEffect(() => { loadDashboardData() }, [loadDashboardData, refreshKey])

    // SSE 订阅
    useEffect(() => {
        const unsub = subscribeSSE(
            () => {
                setRefreshKey(k => k + 1)
            },
            {
                onOpen: () => setConnected(true),
                onError: () => setConnected(false),
            },
        )
        return () => { unsub(); setConnected(false) }
    }, [])

    const title = dashboardData?.project_info?.title || dashboardData?.project_info?.project_info?.title || '未加载'

    return (
        <div className="app-layout">
            <aside className="sidebar">
                <div className="sidebar-header">
                    <h1>PIXEL WRITER HUB</h1>
                    <div className="subtitle">{title}</div>
                </div>
                <nav className="sidebar-nav">
                    {NAV_ITEMS.map(item => (
                        <button
                            key={item.id}
                            className={`nav-item ${page === item.id ? 'active' : ''}`}
                            onClick={() => setPage(item.id)}
                        >
                            <span className="icon">{item.icon}</span>
                            <span>{item.label}</span>
                        </button>
                    ))}
                </nav>
                <div className="live-indicator">
                    <span className={`live-dot ${connected ? '' : 'disconnected'}`} />
                    {connected ? '实时同步中' : '未连接'}
                </div>
            </aside>

            <main className="main-content">
                {page === 'dashboard' && <DashboardPage data={dashboardData} key={refreshKey} onNavigate={setPage} />}
                {page === 'memory' && <MemoryRecallPage data={dashboardData} key={refreshKey} onNavigate={setPage} />}
                {page === 'entities' && <EntitiesPage key={refreshKey} />}
                {page === 'graph' && <GraphPage key={refreshKey} />}
                {page === 'chapters' && <ChaptersPage key={refreshKey} />}
                {page === 'files' && <FilesPage />}
                {page === 'data' && <AllDataPage key={refreshKey} />}
                {page === 'reading' && <ReadingPowerPage key={refreshKey} />}
            </main>
        </div>
    )
}

const NAV_ITEMS = [
    { id: 'dashboard', icon: '✍️', label: '写作驾驶舱' },
    { id: 'memory', icon: '🧠', label: '记忆与召回' },
    { id: 'data', icon: '🧪', label: '全量数据' },
    { id: 'entities', icon: '👤', label: '设定词典' },
    { id: 'graph', icon: '🕸️', label: '关系图谱' },
    { id: 'chapters', icon: '📝', label: '章节一览' },
    { id: 'files', icon: '📁', label: '文档浏览' },
    { id: 'reading', icon: '🔥', label: '追读力' },
]

const FULL_DATA_GROUPS = [
    { key: 'entities', title: '实体', columns: ['id', 'canonical_name', 'type', 'tier', 'first_appearance', 'last_appearance'], domain: 'core' },
    { key: 'chapters', title: '章节', columns: ['chapter', 'title', 'word_count', 'location', 'characters'], domain: 'core' },
    { key: 'scenes', title: '场景', columns: ['chapter', 'scene_index', 'location', 'time', 'summary'], domain: 'core' },
    { key: 'aliases', title: '别名', columns: ['alias', 'entity_id', 'entity_type'], domain: 'core' },
    { key: 'stateChanges', title: '状态变化', columns: ['entity_id', 'field', 'old_value', 'new_value', 'chapter'], domain: 'core' },
    { key: 'relationships', title: '关系', columns: ['from_entity', 'to_entity', 'type', 'chapter', 'description'], domain: 'network' },
    { key: 'relationshipEvents', title: '关系事件', columns: ['from_entity', 'to_entity', 'type', 'chapter', 'event_type', 'description'], domain: 'network' },
    { key: 'readingPower', title: '追读力', columns: ['chapter', 'hook_type', 'hook_strength', 'is_transition', 'override_count', 'debt_balance'], domain: 'network' },
    { key: 'overrides', title: 'Override 合约', columns: ['chapter', 'constraint_type', 'constraint_id', 'due_chapter', 'status'], domain: 'network' },
    { key: 'debts', title: '追读债务', columns: ['id', 'debt_type', 'current_amount', 'interest_rate', 'due_chapter', 'status'], domain: 'network' },
    { key: 'debtEvents', title: '债务事件', columns: ['debt_id', 'event_type', 'amount', 'chapter', 'note'], domain: 'network' },
    { key: 'reviewMetrics', title: '审查指标', columns: ['start_chapter', 'end_chapter', 'overall_score', 'severity_counts', 'created_at'], domain: 'quality' },
    { key: 'invalidFacts', title: '无效事实', columns: ['source_type', 'source_id', 'reason', 'status', 'chapter_discovered'], domain: 'quality' },
    { key: 'checklistScores', title: '写作清单评分', columns: ['chapter', 'template', 'score', 'completion_rate', 'completed_items', 'total_items'], domain: 'quality' },
    { key: 'ragQueries', title: 'RAG 查询日志', columns: ['query_type', 'query', 'results_count', 'latency_ms', 'chapter', 'created_at'], domain: 'ops' },
    { key: 'toolStats', title: '工具调用统计', columns: ['tool_name', 'success', 'retry_count', 'error_code', 'chapter', 'created_at'], domain: 'ops' },
]

const FULL_DATA_DOMAINS = [
    { id: 'overview', label: '总览' },
    { id: 'core', label: '基础档案' },
    { id: 'network', label: '关系与剧情' },
    { id: 'quality', label: '质量审查' },
    { id: 'ops', label: 'RAG 与工具' },
]


// ====================================================================
// 页面 1：数据总览
// ====================================================================

function DashboardPage({ data, onNavigate }) {
    if (!data) return <div className="loading">加载中…</div>

    const info = data.project_info || {}
    const progress = data.progress || {}
    const protagonist = data.protagonist_state || {}
    const strand = data.strand_tracker || {}
    const storyRecall = data.story_recall || {}
    const memoryHealth = data.memory_health || {}
    const writingGuidance = data.writing_guidance || {}
    const readerSignal = data.reader_signal || {}
    const genreProfile = data.genre_profile || {}
    const chapterOutline = data.chapter_outline || ''
    const recentSummaries = data.recent_summaries || []
    const unresolvedForeshadow = storyRecall.priority_foreshadowing || []
    const recentEvents = storyRecall.recent_events || []
    const characterFocus = storyRecall.character_focus || []
    const changeFocus = storyRecall.structured_change_focus || []
    const archiveRecall = storyRecall.archive_recall || {}

    const totalWords = progress.total_words || 0
    const targetWords = info.target_words || 2000000
    const pct = targetWords > 0 ? Math.min(100, (totalWords / targetWords * 100)).toFixed(1) : 0

    // Strand 历史统计
    const history = strand.history || []
    const strandCounts = { quest: 0, fire: 0, constellation: 0 }
    history.forEach(h => { if (strandCounts[h.strand] !== undefined) strandCounts[h.strand]++ })
    const total = history.length || 1
    const healthStatus = memoryHealth.status || 'unknown'
    const healthBadge = healthStatus === 'healthy' ? 'badge-green' : healthStatus === 'busy' ? 'badge-amber' : 'badge-red'

    const quickActions = [
        { label: '查看记忆页', target: 'memory' },
        { label: '打开设定词典', target: 'entities' },
        { label: '查看图谱', target: 'graph' },
    ]

    return (
        <>
            <div className="page-header">
                <h2>✍️ 写作驾驶舱</h2>
                <span className="card-badge badge-blue">{info.genre || '未知题材'}</span>
            </div>

            <div className="card cockpit-hero">
                <div className="cockpit-hero-top">
                    <div>
                        <div className="cockpit-kicker">当前写作任务</div>
                        <div className="cockpit-title">第 {progress.current_chapter || data.chapter || 0} 章 · {info.title || '未命名项目'}</div>
                        <div className="cockpit-subtitle">
                            {protagonist.name || '未设定主角'} · {protagonist.power?.realm || '未知境界'}
                            {protagonist.location?.current ? ` · ${protagonist.location.current}` : ''}
                        </div>
                    </div>
                    <div className={`card-badge ${healthBadge}`}>{healthStatus}</div>
                </div>
                <div className="cockpit-hero-meta">
                    <span>总字数 {formatNumber(totalWords)} / {formatNumber(targetWords)}</span>
                    <span>卷 {progress.current_volume || 1} · 目标 {info.target_chapters || '?'}</span>
                    <span>召回信号 {unresolvedForeshadow.length}</span>
                    <span>Gap {memoryHealth.consolidation_gap || 0}</span>
                </div>
                <div className="progress-track cockpit-progress">
                    <div className="progress-fill" style={{ width: `${pct}%` }} />
                </div>
                <div className="cockpit-actions">
                    {quickActions.map(action => (
                        <button key={action.target} className="quick-action-btn" onClick={() => onNavigate?.(action.target)}>
                            {action.label}
                        </button>
                    ))}
                </div>
            </div>

            <div className="split-layout">
                <div className="split-main">
                    <div className="card dashboard-section-card">
                        <div className="card-header">
                            <span className="card-title">本章焦点</span>
                            <span className="card-badge badge-purple">Ch.{progress.current_chapter || data.chapter || 0}</span>
                        </div>
                        <div className="entity-detail">
                            <p className="entity-desc">{chapterOutline || '暂无本章大纲'}</p>
                            {Array.isArray(writingGuidance.guidance_items) && writingGuidance.guidance_items.length > 0 ? (
                                <div className="entity-current-block">
                                    <strong>写作建议：</strong>
                                    <ul className="summary-list compact">
                                        {writingGuidance.guidance_items.slice(0, 3).map((item, index) => <li key={index}>{item}</li>)}
                                    </ul>
                                </div>
                            ) : null}
                            {recentSummaries.length > 0 ? (
                                <div className="entity-current-block">
                                    <strong>最近摘要：</strong>
                                    <ul className="summary-list">
                                        {recentSummaries.map((item, index) => {
                                            const chapter = item?.chapter || '?'
                                            const summary = item?.summary || ''
                                            return <li key={index}>Ch.{chapter}: {summary}</li>
                                        })}
                                    </ul>
                                </div>
                            ) : null}
                        </div>
                    </div>

                    <div className="card dashboard-section-card">
                        <div className="entity-detail">
                            <div className="card-header-inline">
                                <strong>高优先级召回</strong>
                                <span className="card-badge badge-amber">{storyRecall.recall_policy?.mode || 'normal'}</span>
                            </div>
                            {unresolvedForeshadow.length > 0 ? (
                                <ul className="summary-list compact">
                                    {unresolvedForeshadow.slice(0, 3).map((item, index) => (
                                        <li key={index}>{item.content || item.description || item.event || '—'} · {item.status || '未知'}</li>
                                    ))}
                                </ul>
                            ) : <p>当前没有需要优先召回的伏笔</p>}

                            {recentEvents.length > 0 ? (
                                <>
                                    <div className="card-header-inline">
                                        <strong>最近事件</strong>
                                    </div>
                                    <ul className="summary-list compact">
                                        {recentEvents.slice(0, 3).map((item, index) => (
                                            <li key={index}>Ch.{item.ch || item.chapter || '?'}: {item.event || item.content || '—'}</li>
                                        ))}
                                    </ul>
                                </>
                            ) : null}

                            {characterFocus.length > 0 ? (
                                <>
                                    <div className="card-header-inline">
                                        <strong>关键人物</strong>
                                    </div>
                                    <ul className="summary-list compact">
                                        {characterFocus.slice(0, 3).map((item, index) => (
                                            <li key={index}>{item.name || '未命名角色'}: {item.current_state || '—'}</li>
                                        ))}
                                    </ul>
                                </>
                            ) : null}

                            {changeFocus.length > 0 ? (
                                <>
                                    <div className="card-header-inline">
                                        <strong>结构化变化</strong>
                                    </div>
                                    <ul className="summary-list compact">
                                        {changeFocus.slice(0, 3).map((item, index) => (
                                            <li key={index}>{item.entity_id || '—'}.{item.field || '—'}: {item.old_value || '—'} → {item.new_value || '—'}</li>
                                        ))}
                                    </ul>
                                </>
                            ) : null}
                        </div>
                    </div>
                </div>

                <div className="split-side">
                    <div className="card dashboard-section-card">
                        <div className="card-header">
                            <span className="card-title">记忆健康</span>
                            <span className={`card-badge ${healthBadge}`}>{healthStatus}</span>
                        </div>
                        <div className="entity-detail">
                            <p><strong>回收状态：</strong>{memoryHealth.should_recall_story_memory ? '启用' : '停用'}</p>
                            <p><strong>last consolidated：</strong>Ch.{memoryHealth.last_consolidated_chapter || 0}</p>
                            <p><strong>consolidation gap：</strong>{memoryHealth.consolidation_gap || 0}</p>
                            <p><strong>召回信号：</strong>{memoryHealth.signal_count || 0}</p>
                            <p><strong>未回收伏笔：</strong>{memoryHealth.priority_foreshadowing_count || 0}</p>
                            <p><strong>归档召回：</strong>{memoryHealth.archive_available ? '可用' : '未命中'}</p>
                            {memoryHealth.memory_stale ? <p className="debt-positive">记忆层偏旧，建议优先整理。</p> : null}
                        </div>
                    </div>

                    <div className="card dashboard-section-card">
                        <div className="card-header">
                            <span className="card-title">节奏分布</span>
                            <span className="card-badge badge-purple">{strand.current_dominant || '?'}</span>
                        </div>
                        <div className="strand-bar">
                            <div className="segment strand-quest" style={{ width: `${(strandCounts.quest / total * 100).toFixed(1)}%` }} />
                            <div className="segment strand-fire" style={{ width: `${(strandCounts.fire / total * 100).toFixed(1)}%` }} />
                            <div className="segment strand-constellation" style={{ width: `${(strandCounts.constellation / total * 100).toFixed(1)}%` }} />
                        </div>
                        <div className="strand-legend">
                            <span>🔵 Quest {(strandCounts.quest / total * 100).toFixed(0)}%</span>
                            <span>🔴 Fire {(strandCounts.fire / total * 100).toFixed(0)}%</span>
                            <span>🟣 Constellation {(strandCounts.constellation / total * 100).toFixed(0)}%</span>
                        </div>
                    </div>

                    <div className="card dashboard-section-card">
                        <div className="card-header">
                            <span className="card-title">题材与阅读信号</span>
                        </div>
                        <div className="entity-detail">
                            <p><strong>题材：</strong>{info.genre || '未知'}</p>
                            <p><strong>复合题材：</strong>{Array.isArray(genreProfile.genres) && genreProfile.genres.length > 0 ? genreProfile.genres.join(' + ') : '—'}</p>
                            <p><strong>最近审查均分：</strong>{readerSignal.review_trend?.overall_avg ?? '—'}</p>
                            <p><strong>低分区间：</strong>{Array.isArray(readerSignal.low_score_ranges) ? readerSignal.low_score_ranges.length : 0}</p>
                        </div>
                    </div>
                </div>
            </div>
        </>
    )
}

function MemoryRecallPage({ data, onNavigate }) {
    if (!data) return <div className="loading">加载中…</div>

    const storyRecall = data.story_recall || {}
    const memoryHealth = data.memory_health || {}
    const writingGuidance = data.writing_guidance || {}
    const archiveRecall = storyRecall.archive_recall || {}
    const recallPolicy = storyRecall.recall_policy || {}
    const memorySections = [
        { id: 'recall-priority', label: '高优先级召回' },
        { id: 'recall-archive', label: '归档召回' },
        { id: 'recall-health', label: '记忆健康' },
        { id: 'recall-guidance', label: '写作建议' },
    ]
    const jumpTo = (sectionId) => {
        document.getElementById(sectionId)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }

    return (
        <>
            <div className="page-header">
                <div>
                    <h2>🧠 记忆与召回</h2>
                    <p className="page-subtitle">先看摘要，必要时再展开历史与归档。</p>
                </div>
                <div className="page-header-actions">
                    <span className={`card-badge ${memoryHealth.memory_stale ? 'badge-amber' : 'badge-green'}`}>
                        {memoryHealth.memory_stale ? '需要整理' : '稳定'}
                    </span>
                    <button className="quick-action-btn" onClick={() => onNavigate?.('dashboard')}>回到驾驶舱</button>
                    <button className="quick-action-btn" onClick={() => onNavigate?.('data')}>看全量数据</button>
                </div>
            </div>

            <div className="memory-section-nav">
                {memorySections.map(section => (
                    <button
                        key={section.id}
                        className="memory-section-btn"
                        onClick={() => jumpTo(section.id)}
                    >
                        {section.label}
                    </button>
                ))}
            </div>

            <div className="card dashboard-section-card memory-summary-card">
                <div className="memory-summary-strip">
                    <div className="memory-summary-item">
                        <span className="stat-label">召回模式</span>
                        <span className="stat-value plain">{recallPolicy.mode || 'normal'}</span>
                        <span className="stat-sub">signals {recallPolicy.signal_count || 0} · gap {recallPolicy.consolidation_gap || 0}</span>
                    </div>
                    <div className="memory-summary-item">
                        <span className="stat-label">归档可用</span>
                        <span className="stat-value">{memoryHealth.archive_available ? '是' : '否'}</span>
                        <span className="stat-sub">plot {memoryHealth.archive_counts?.plot_threads || 0} · event {memoryHealth.archive_counts?.recent_events || 0}</span>
                    </div>
                    <div className="memory-summary-item">
                        <span className="stat-label">未回收伏笔</span>
                        <span className="stat-value">{memoryHealth.priority_foreshadowing_count || 0}</span>
                        <span className="stat-sub">recent events {memoryHealth.recent_events_count || 0}</span>
                    </div>
                    <div className="memory-summary-item">
                        <span className="stat-label">写作评分</span>
                        <span className="stat-value plain">{writingGuidance.checklist_score?.score ?? '—'}</span>
                        <span className="stat-sub">completion {writingGuidance.checklist_score?.completion_rate ?? '—'}</span>
                    </div>
                </div>
            </div>

            <div className="split-layout">
                <div className="split-main">
                    <div className="card dashboard-section-card" id="recall-priority">
                        <div className="card-header">
                            <span className="card-title">高优先级召回</span>
                            <span className="card-badge badge-amber">{storyRecall.priority_foreshadowing?.length || 0} 条</span>
                        </div>
                        <div className="entity-detail">
                            <p><strong>策略：</strong>mode={recallPolicy.mode || 'normal'} · should_recall={String(recallPolicy.should_recall_story_memory)}</p>
                            <p><strong>提示：</strong>{Array.isArray(recallPolicy.reasons) && recallPolicy.reasons.length > 0 ? recallPolicy.reasons.slice(0, 3).join(' / ') : '当前召回按默认权重执行'}</p>
                            {Array.isArray(storyRecall.priority_foreshadowing) && storyRecall.priority_foreshadowing.length > 0 ? (
                                <ul className="summary-list compact">
                                    {storyRecall.priority_foreshadowing.slice(0, 5).map((item, index) => (
                                        <li key={index}>
                                            {item.name || item.content || item.event || '未命名伏笔'}
                                            {item.urgency !== undefined ? `（urgency=${item.urgency}）` : ''}
                                        </li>
                                    ))}
                                </ul>
                            ) : <p>暂无活跃召回信号。</p>}
                        </div>
                    </div>

                    <div className="card dashboard-section-card" id="recall-archive">
                        <div className="card-header">
                            <span className="card-title">归档召回</span>
                            <span className="card-badge badge-purple">{archiveRecall.plot_threads?.length || 0} / {archiveRecall.recent_events?.length || 0}</span>
                        </div>
                        {archiveRecall.plot_threads?.length > 0 ? (
                            <details className="memory-details" open>
                                <summary>归档伏笔 {archiveRecall.plot_threads.length} 条</summary>
                                <ul className="summary-list compact">
                                    {archiveRecall.plot_threads.slice(0, 4).map((item, index) => (
                                        <li key={index}>{item.content || item.event || '—'}（tier={item.memory_tier || 'archive'} · score={item.archive_score ?? '—'}）</li>
                                    ))}
                                </ul>
                            </details>
                        ) : <div className="empty-state compact"><p>暂无归档伏笔召回</p></div>}

                        {archiveRecall.recent_events?.length > 0 ? (
                            <details className="memory-details">
                                <summary>归档事件 {archiveRecall.recent_events.length} 条</summary>
                                <ul className="summary-list compact">
                                    {archiveRecall.recent_events.slice(0, 4).map((item, index) => (
                                        <li key={index}>Ch.{item.ch || item.chapter || '?'}: {item.event || '—'}（score={item.archive_score ?? '—'}）</li>
                                    ))}
                                </ul>
                            </details>
                        ) : null}

                        {archiveRecall.structured_change_focus?.length > 0 ? (
                            <details className="memory-details">
                                <summary>归档变化 {archiveRecall.structured_change_focus.length} 条</summary>
                                <ul className="summary-list compact">
                                    {archiveRecall.structured_change_focus.slice(0, 4).map((item, index) => (
                                        <li key={index}>{item.entity_id || '—'}.{item.field || '—'}（tier={item.memory_tier || 'archive'} · score={item.archive_score ?? '—'}）</li>
                                    ))}
                                </ul>
                            </details>
                        ) : null}
                    </div>
                </div>

                <div className="split-side">
                    <div className="card dashboard-section-card" id="recall-health">
                        <div className="card-header">
                            <span className="card-title">记忆健康</span>
                            <span className={`card-badge ${memoryHealth.memory_stale ? 'badge-red' : 'badge-green'}`}>{memoryHealth.status || 'unknown'}</span>
                        </div>
                        <div className="entity-detail compact">
                            <p><strong>last consolidated：</strong>Ch.{memoryHealth.last_consolidated_chapter || 0}</p>
                            <p><strong>gap：</strong>{memoryHealth.consolidation_gap || 0}</p>
                            <p><strong>signals：</strong>{memoryHealth.signal_count || 0}</p>
                            <p><strong>characters：</strong>{memoryHealth.character_focus_count || 0}</p>
                            <p><strong>changes：</strong>{memoryHealth.structured_change_count || 0}</p>
                            <p><strong>archive：</strong>{memoryHealth.archive_available ? 'available' : 'empty'}</p>
                        </div>
                    </div>

                    <div className="card dashboard-section-card" id="recall-guidance">
                        <div className="card-header">
                            <span className="card-title">写作建议</span>
                            <span className="card-badge badge-cyan">{writingGuidance.checklist?.length || 0} 项</span>
                        </div>
                        <p className="entity-desc">{Array.isArray(writingGuidance.guidance_items) && writingGuidance.guidance_items.length > 0 ? writingGuidance.guidance_items[0] : '暂无写作建议'}</p>
                        {Array.isArray(writingGuidance.guidance_items) && writingGuidance.guidance_items.length > 1 ? (
                            <details className="memory-details">
                                <summary>展开更多建议 {Math.min(writingGuidance.guidance_items.length - 1, 5)} 条</summary>
                                <ul className="summary-list compact">
                                    {writingGuidance.guidance_items.slice(1, 6).map((item, index) => <li key={index}>{item}</li>)}
                                </ul>
                            </details>
                        ) : null}
                    </div>
                </div>
            </div>
        </>
    )
}

function AllDataPage() {
    return <MergedDataView />
}


// ====================================================================
// 页面 2：设定词典
// ====================================================================

function EntitiesPage() {
    const [entities, setEntities] = useState([])
    const [typeFilter, setTypeFilter] = useState('')
    const [selected, setSelected] = useState(null)
    const [changes, setChanges] = useState([])

    useEffect(() => {
        fetchJSON('/api/entities').then(setEntities).catch(() => { })
    }, [])

    useEffect(() => {
        if (selected) {
            fetchJSON('/api/state-changes', { entity: selected.id, limit: 30 }).then(setChanges).catch(() => setChanges([]))
        }
    }, [selected])

    const types = [...new Set(entities.map(e => e.type))].sort()
    const filteredEntities = typeFilter ? entities.filter(e => e.type === typeFilter) : entities

    return (
        <>
            <div className="page-header">
                <h2>👤 设定词典</h2>
                <span className="card-badge badge-green">{filteredEntities.length} / {entities.length} 个实体</span>
            </div>

            <div className="filter-group">
                <button className={`filter-btn ${typeFilter === '' ? 'active' : ''}`} onClick={() => setTypeFilter('')}>全部</button>
                {types.map(t => (
                    <button key={t} className={`filter-btn ${typeFilter === t ? 'active' : ''}`} onClick={() => setTypeFilter(t)}>{t}</button>
                ))}
            </div>

            <div className="split-layout">
                <div className="split-main">
                    <div className="card">
                        <div className="table-wrap">
                            <table className="data-table">
                                <thead><tr><th>名称</th><th>类型</th><th>层级</th><th>首现</th><th>末现</th></tr></thead>
                                <tbody>
                                    {filteredEntities.map(e => (
                                        <tr
                                            key={e.id}
                                            role="button"
                                            tabIndex={0}
                                            className={`entity-row ${selected?.id === e.id ? 'selected' : ''}`}
                                            onKeyDown={evt => (evt.key === 'Enter' || evt.key === ' ') && (evt.preventDefault(), setSelected(e))}
                                            onClick={() => setSelected(e)}
                                        >
                                            <td className={e.is_protagonist ? 'entity-name protagonist' : 'entity-name'}>
                                                {e.canonical_name} {e.is_protagonist ? '⭐' : ''}
                                            </td>
                                            <td><span className="card-badge badge-blue">{e.type}</span></td>
                                            <td>{e.tier}</td>
                                            <td>{e.first_appearance || '—'}</td>
                                            <td>{e.last_appearance || '—'}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                {selected && (
                    <div className="split-side">
                        <div className="card">
                            <div className="card-header">
                                <span className="card-title">{selected.canonical_name}</span>
                                <span className="card-badge badge-purple">{selected.tier}</span>
                            </div>
                            <div className="entity-detail">
                                <p><strong>类型：</strong>{selected.type}</p>
                                <p><strong>ID：</strong><code>{selected.id}</code></p>
                                {selected.desc && <p className="entity-desc">{selected.desc}</p>}
                                {selected.current_json && (
                                    <div className="entity-current-block">
                                        <strong>当前状态：</strong>
                                        <pre className="entity-json">
                                            {formatJSON(selected.current_json)}
                                        </pre>
                                    </div>
                                )}
                            </div>
                            {changes.length > 0 ? (
                                <div className="entity-history">
                                    <div className="card-title">状态变化历史</div>
                                    <div className="table-wrap">
                                        <table className="data-table">
                                            <thead><tr><th>章</th><th>字段</th><th>变化</th></tr></thead>
                                            <tbody>
                                                {changes.map((c, i) => (
                                                    <tr key={i}>
                                                        <td>{c.chapter}</td>
                                                        <td>{c.field}</td>
                                                        <td>{c.old_value} → {c.new_value}</td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            ) : null}
                        </div>
                    </div>
                )}
            </div>
        </>
    )
}


// ====================================================================
// 页面 3：3D 宇宙关系图谱
// ====================================================================

function GraphPage() {
    const [relationships, setRelationships] = useState([])
    const [graphData, setGraphData] = useState({ nodes: [], links: [] })

    useEffect(() => {
        Promise.all([
            fetchJSON('/api/relationships', { limit: 1000 }),
            fetchJSON('/api/entities'),
        ]).then(([rels, ents]) => {
            setRelationships(rels)
            const typeColors = {
                '角色': '#4f8ff7', '地点': '#34d399', '星球': '#22d3ee', '神仙': '#f59e0b',
                '势力': '#8b5cf6', '招式': '#ef4444', '法宝': '#ec4899'
            }
            const relatedIds = new Set()
            rels.forEach(r => { relatedIds.add(r.from_entity); relatedIds.add(r.to_entity) })
            const entityMap = {}
            ents.forEach(e => { entityMap[e.id] = e })

            const nodes = [...relatedIds].map(id => ({
                id,
                name: entityMap[id]?.canonical_name || id,
                val: (entityMap[id]?.tier === 'S' ? 8 : entityMap[id]?.tier === 'A' ? 5 : 2),
                color: typeColors[entityMap[id]?.type] || '#5c6078'
            }))
            const links = rels.map(r => ({
                source: r.from_entity,
                target: r.to_entity,
                name: r.type
            }))
            setGraphData({ nodes, links })
        }).catch(() => { })
    }, [])

    return (
        <>
            <div className="page-header">
                <h2>🕸️ 关系图谱</h2>
                <span className="card-badge badge-blue">{relationships.length} 条引力链接</span>
            </div>
            <div className="card graph-shell">
                <ForceGraph3D
                    graphData={graphData}
                    nodeLabel="name"
                    nodeColor="color"
                    nodeRelSize={6}
                    linkColor={() => 'rgba(127, 90, 240, 0.35)'}
                    linkWidth={1}
                    linkDirectionalParticles={2}
                    linkDirectionalParticleWidth={1.5}
                    linkDirectionalParticleSpeed={d => 0.005 + Math.random() * 0.005}
                    backgroundColor="#fffaf0"
                    showNavInfo={false}
                />
            </div>
        </>
    )
}



// ====================================================================
// 页面 4：章节一览
// ====================================================================

function ChaptersPage() {
    const [chapters, setChapters] = useState([])

    useEffect(() => {
        fetchJSON('/api/chapters').then(setChapters).catch(() => { })
    }, [])

    const totalWords = chapters.reduce((s, c) => s + (c.word_count || 0), 0)

    return (
        <>
            <div className="page-header">
                <h2>📝 章节一览</h2>
                <span className="card-badge badge-green">{chapters.length} 章 · {formatNumber(totalWords)} 字</span>
            </div>
            <div className="card">
                <div className="table-wrap">
                    <table className="data-table">
                        <thead><tr><th>章节</th><th>标题</th><th>字数</th><th>地点</th><th>角色</th></tr></thead>
                        <tbody>
                            {chapters.map(c => (
                                <tr key={c.chapter}>
                                    <td className="chapter-no">第 {c.chapter} 章</td>
                                    <td>{c.title || '—'}</td>
                                    <td>{formatNumber(c.word_count || 0)}</td>
                                    <td>{c.location || '—'}</td>
                                    <td className="truncate chapter-characters">{c.characters || '—'}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
                {chapters.length === 0 ? <div className="empty-state"><div className="empty-icon">📭</div><p>暂无章节数据</p></div> : null}
            </div>
        </>
    )
}


// ====================================================================
// 页面 5：文档浏览
// ====================================================================

function FilesPage() {
    const [tree, setTree] = useState({})
    const [selectedPath, setSelectedPath] = useState(null)
    const [content, setContent] = useState('')

    useEffect(() => {
        fetchJSON('/api/files/tree').then(setTree).catch(() => { })
    }, [])

    useEffect(() => {
        if (selectedPath) {
            fetchJSON('/api/files/read', { path: selectedPath })
                .then(d => setContent(d.content))
                .catch(() => setContent('[读取失败]'))
        }
    }, [selectedPath])

    useEffect(() => {
        if (selectedPath) return
        const first = findFirstFilePath(tree)
        if (first) setSelectedPath(first)
    }, [tree, selectedPath])

    return (
        <>
            <div className="page-header">
                <h2>📁 文档浏览</h2>
            </div>
            <div className="file-layout">
                <div className="file-tree-pane">
                    {Object.entries(tree).map(([folder, items]) => (
                        <div key={folder} className="folder-block">
                            <div className="folder-title">📂 {folder}</div>
                            <ul className="file-tree">
                                <TreeNodes items={items} selected={selectedPath} onSelect={setSelectedPath} />
                            </ul>
                        </div>
                    ))}
                </div>
                <div className="file-content-pane">
                    {selectedPath ? (
                        <div>
                            <div className="selected-path">{selectedPath}</div>
                            <div className="file-preview">{content}</div>
                        </div>
                    ) : (
                        <div className="empty-state"><div className="empty-icon">📄</div><p>选择左侧文件以预览内容</p></div>
                    )}
                </div>
            </div>
        </>
    )
}


// ====================================================================
// 页面 6：追读力
// ====================================================================

function ReadingPowerPage() {
    const [data, setData] = useState([])

    useEffect(() => {
        fetchJSON('/api/reading-power', { limit: 50 }).then(setData).catch(() => { })
    }, [])

    return (
        <>
            <div className="page-header">
                <h2>🔥 追读力分析</h2>
                <span className="card-badge badge-amber">{data.length} 章数据</span>
            </div>
            <div className="card">
                <div className="table-wrap">
                    <table className="data-table">
                        <thead><tr><th>章节</th><th>钩子类型</th><th>钩子强度</th><th>过渡章</th><th>Override</th><th>债务余额</th></tr></thead>
                        <tbody>
                            {data.map(r => (
                                <tr key={r.chapter}>
                                    <td className="chapter-no">第 {r.chapter} 章</td>
                                    <td>{r.hook_type || '—'}</td>
                                    <td>
                                        <span className={`card-badge ${r.hook_strength === 'strong' ? 'badge-green' : r.hook_strength === 'weak' ? 'badge-red' : 'badge-amber'}`}>
                                            {r.hook_strength || '—'}
                                        </span>
                                    </td>
                                    <td>{r.is_transition ? '✅' : '—'}</td>
                                    <td>{r.override_count || 0}</td>
                                    <td className={r.debt_balance > 0 ? 'debt-positive' : 'debt-normal'}>{(r.debt_balance || 0).toFixed(2)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
                {data.length === 0 ? <div className="empty-state"><div className="empty-icon">🔥</div><p>暂无追读力数据</p></div> : null}
            </div>
        </>
    )
}

function findFirstFilePath(tree) {
    const roots = Object.values(tree || {})
    for (const items of roots) {
        const p = walkFirstFile(items)
        if (p) return p
    }
    return null
}

function walkFirstFile(items) {
    if (!Array.isArray(items)) return null
    for (const item of items) {
        if (item?.type === 'file' && item?.path) return item.path
        if (item?.type === 'dir' && Array.isArray(item.children)) {
            const p = walkFirstFile(item.children)
            if (p) return p
        }
    }
    return null
}


// ====================================================================
// 数据总览内嵌：全量数据视图
// ====================================================================

function MergedDataView() {
    const [loading, setLoading] = useState(true)
    const [payload, setPayload] = useState({})
    const [domain, setDomain] = useState('overview')

    useEffect(() => {
        let disposed = false

        async function loadAll() {
            setLoading(true)
            const requests = [
                ['entities', fetchJSON('/api/entities')],
                ['chapters', fetchJSON('/api/chapters')],
                ['scenes', fetchJSON('/api/scenes', { limit: 200 })],
                ['relationships', fetchJSON('/api/relationships', { limit: 300 })],
                ['relationshipEvents', fetchJSON('/api/relationship-events', { limit: 200 })],
                ['readingPower', fetchJSON('/api/reading-power', { limit: 100 })],
                ['reviewMetrics', fetchJSON('/api/review-metrics', { limit: 50 })],
                ['stateChanges', fetchJSON('/api/state-changes', { limit: 120 })],
                ['aliases', fetchJSON('/api/aliases')],
                ['overrides', fetchJSON('/api/overrides', { limit: 120 })],
                ['debts', fetchJSON('/api/debts', { limit: 120 })],
                ['debtEvents', fetchJSON('/api/debt-events', { limit: 150 })],
                ['invalidFacts', fetchJSON('/api/invalid-facts', { limit: 120 })],
                ['ragQueries', fetchJSON('/api/rag-queries', { limit: 150 })],
                ['toolStats', fetchJSON('/api/tool-stats', { limit: 200 })],
                ['checklistScores', fetchJSON('/api/checklist-scores', { limit: 120 })],
            ]

            const entries = await Promise.all(
                requests.map(async ([key, p]) => {
                    try {
                        const val = await p
                        return [key, val]
                    } catch {
                        return [key, []]
                    }
                }),
            )
            if (!disposed) {
                setPayload(Object.fromEntries(entries))
                setLoading(false)
            }
        }

        loadAll()
        return () => { disposed = true }
    }, [])

    if (loading) return <div className="loading">加载全量数据中…</div>

    const groups = domain === 'overview'
        ? FULL_DATA_GROUPS
        : FULL_DATA_GROUPS.filter(g => g.domain === domain)
    const totalRows = FULL_DATA_GROUPS.reduce((sum, g) => sum + (payload[g.key] || []).length, 0)
    const nonEmptyGroups = FULL_DATA_GROUPS.filter(g => (payload[g.key] || []).length > 0).length
    const maxChapter = FULL_DATA_GROUPS.reduce((max, g) => {
        const rows = payload[g.key] || []
        rows.slice(0, 120).forEach(r => {
            const c = extractChapter(r)
            if (c > max) max = c
        })
        return max
    }, 0)
    const domainStats = FULL_DATA_DOMAINS.filter(d => d.id !== 'overview').map(d => {
        const ds = FULL_DATA_GROUPS.filter(g => g.domain === d.id)
        const rowCount = ds.reduce((sum, g) => sum + (payload[g.key] || []).length, 0)
        const filled = ds.filter(g => (payload[g.key] || []).length > 0).length
        return { ...d, rowCount, filled, total: ds.length }
    })

    return (
        <>
            <div className="page-header section-page-header">
                <h2>🧪 全量数据视图</h2>
                <span className="card-badge badge-cyan">{FULL_DATA_GROUPS.length} 类数据源</span>
            </div>

            <div className="demo-summary-grid">
                <div className="card stat-card">
                    <span className="stat-label">总记录数</span>
                    <span className="stat-value">{formatNumber(totalRows)}</span>
                    <span className="stat-sub">当前返回的全部数据行</span>
                </div>
                <div className="card stat-card">
                    <span className="stat-label">已覆盖数据源</span>
                    <span className="stat-value plain">{nonEmptyGroups}/{FULL_DATA_GROUPS.length}</span>
                    <span className="stat-sub">有数据的表 / 总表数</span>
                </div>
                <div className="card stat-card">
                    <span className="stat-label">最新章节触达</span>
                    <span className="stat-value plain">{maxChapter > 0 ? `第 ${maxChapter} 章` : '—'}</span>
                    <span className="stat-sub">按可识别 chapter 字段估算</span>
                </div>
                <div className="card stat-card">
                    <span className="stat-label">当前视图</span>
                    <span className="stat-value plain">{FULL_DATA_DOMAINS.find(d => d.id === domain)?.label}</span>
                    <span className="stat-sub">{groups.length} 个数据分组</span>
                </div>
            </div>

            <div className="demo-domain-tabs">
                {FULL_DATA_DOMAINS.map(item => (
                    <button
                        key={item.id}
                        className={`demo-domain-tab ${domain === item.id ? 'active' : ''}`}
                        onClick={() => setDomain(item.id)}
                    >
                        {item.label}
                    </button>
                ))}
            </div>

            {domain === 'overview' ? (
                <div className="demo-domain-grid">
                    {domainStats.map(ds => (
                        <div className="card" key={ds.id}>
                            <div className="card-header">
                                <span className="card-title">{ds.label}</span>
                                <span className="card-badge badge-purple">{ds.filled}/{ds.total}</span>
                            </div>
                            <div className="domain-stat-number">{formatNumber(ds.rowCount)}</div>
                            <div className="stat-sub">该数据域总记录数</div>
                        </div>
                    ))}
                </div>
            ) : null}

            {groups.map(g => {
                const count = (payload[g.key] || []).length
                return (
                    <div className="card demo-group-card" key={g.key}>
                        <div className="card-header">
                            <span className="card-title">{g.title}</span>
                            <span className={`card-badge ${count > 0 ? 'badge-blue' : 'badge-amber'}`}>{count} 条</span>
                        </div>
                        <MiniTable
                            rows={payload[g.key] || []}
                            columns={g.columns}
                            pageSize={12}
                        />
                    </div>
                )
            })}
        </>
    )
}

function MiniTable({ rows, columns, pageSize = 12 }) {
    const [page, setPage] = useState(1)

    useEffect(() => {
        setPage(1)
    }, [rows, columns, pageSize])

    if (!rows || rows.length === 0) {
        return <div className="empty-state compact"><p>暂无数据</p></div>
    }

    const totalPages = Math.max(1, Math.ceil(rows.length / pageSize))
    const safePage = Math.min(page, totalPages)
    const start = (safePage - 1) * pageSize
    const list = rows.slice(start, start + pageSize)

    return (
        <>
            <div className="table-wrap">
                <table className="data-table">
                    <thead>
                        <tr>{columns.map(c => <th key={c}>{c}</th>)}</tr>
                    </thead>
                    <tbody>
                        {list.map((row, i) => (
                            <tr key={i}>
                                {columns.map(c => (
                                    <td key={c} className="truncate" style={{ maxWidth: 240 }}>
                                        {formatCell(row?.[c])}
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            <div className="table-pagination">
                <button
                    className="page-btn"
                    type="button"
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={safePage <= 1}
                >
                    上一页
                </button>
                <span className="page-info">
                    第 {safePage} / {totalPages} 页 · 共 {rows.length} 条
                </span>
                <button
                    className="page-btn"
                    type="button"
                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                    disabled={safePage >= totalPages}
                >
                    下一页
                </button>
            </div>
        </>
    )
}

function extractChapter(row) {
    if (!row || typeof row !== 'object') return 0
    const candidates = [
        row.chapter,
        row.start_chapter,
        row.end_chapter,
        row.chapter_discovered,
        row.first_appearance,
        row.last_appearance,
    ]
    for (const c of candidates) {
        const n = Number(c)
        if (Number.isFinite(n) && n > 0) return n
    }
    return 0
}


// ====================================================================
// 子组件：文件树递归
// ====================================================================

function TreeNodes({ items, selected, onSelect, depth = 0 }) {
    const [expanded, setExpanded] = useState({})
    if (!items || items.length === 0) return null

    return items.map((item, i) => {
        const key = item.path || `${depth}-${i}`
        if (item.type === 'dir') {
            const isOpen = expanded[key]
            return (
                <li key={key}>
                    <div
                        className="tree-item"
                        role="button"
                        tabIndex={0}
                        onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), setExpanded(prev => ({ ...prev, [key]: !prev[key] })))}
                        onClick={() => setExpanded(prev => ({ ...prev, [key]: !prev[key] }))}
                    >
                        <span className="tree-icon">{isOpen ? '📂' : '📁'}</span>
                        <span>{item.name}</span>
                    </div>
                    {isOpen && item.children && (
                        <ul className="tree-children">
                            <TreeNodes items={item.children} selected={selected} onSelect={onSelect} depth={depth + 1} />
                        </ul>
                    )}
                </li>
            )
        }
        return (
            <li key={key}>
                <div
                    className={`tree-item ${selected === item.path ? 'active' : ''}`}
                    role="button"
                    tabIndex={0}
                    onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onSelect(item.path))}
                    onClick={() => onSelect(item.path)}
                >
                    <span className="tree-icon">📄</span>
                    <span>{item.name}</span>
                </div>
            </li>
        )
    })
}


// ====================================================================
// 辅助：数字格式化
// ====================================================================

function formatNumber(n) {
    if (n >= 10000) return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 1 }).format(n / 10000) + ' 万'
    return new Intl.NumberFormat('zh-CN').format(n)
}

function formatJSON(str) {
    try {
        return JSON.stringify(JSON.parse(str), null, 2)
    } catch {
        return str
    }
}

function formatCell(v) {
    if (v === null || v === undefined) return '—'
    if (typeof v === 'boolean') return v ? 'true' : 'false'
    if (typeof v === 'object') {
        try {
            return JSON.stringify(v)
        } catch {
            return String(v)
        }
    }
    const s = String(v)
    return s.length > 180 ? `${s.slice(0, 180)}...` : s
}
