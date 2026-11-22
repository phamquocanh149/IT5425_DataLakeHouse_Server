import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import './styles.css';
type Dict = Record<string, any>;
const API = '/api/portal/v1';
const colors: Record<string, string> = { '0': '#c6dbd5', 'D0': '#efce55', 'D1': '#efa95a', 'D2': '#e37b45', 'D3': '#bd4939', 'D4': '#742d3c' };
const labels: Record<string, string> = { '0': 'Không hạn', 'D0': 'Khô bất thường', 'D1': 'Hạn vừa', 'D2': 'Hạn nặng', 'D3': 'Hạn cực đoan', 'D4': 'Hạn đặc biệt' };
let csrf = '';
async function api(path: string, options: RequestInit = {}): Promise<any> {
    const response = await fetch(API + path, { ...options, headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf, ...options.headers } });
    if (response.status === 401)
        window.dispatchEvent(new Event('portal-session-expired'));
    if (!response.ok) {
        let body: Dict = {};
        try {
            body = await response.json();
        }
        catch { }
        ;
        const error: any = new Error(body.error?.message || 'Không thể kết nối dịch vụ');
        error.status = response.status;
        error.code = body.error?.code;
        error.requestId = body.request_id;
        throw error;
    }
    return response.status === 204 ? null : response.json();
}
const num = (n: number = 0) => new Intl.NumberFormat('vi-VN').format(n);
const day = (v: string = '') => v ? new Intl.DateTimeFormat('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric', timeZone: 'UTC' }).format(new Date(v)) : '—';
const size = (n: number) => n >= 1048576 ? (n / 1048576).toFixed(1) + ' MB' : num(n) + ' bytes';
const short = (v: string = '') => v ? v.slice(0, 14) + '…' : '—';
function Icon({ name, size: s = 20 }: {
    name: string;
    size?: number;
}) {
    const paths: Record<string, React.ReactNode> = { overview: <><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/></>, catalog: <><path d="M3 7h18M3 12h18M3 17h18"/><path d="M7 5v14"/></>, layers: <><path d="m12 3 10 5-10 5L2 8zM2 12l10 5 10-5M2 16l10 5 10-5"/></>, download: <><path d="M12 3v12m-4-4 4 4 4-4M4 15v5h16v-5"/></>, map: <><path d="m3 5 6-2 6 2 6-2v16l-6 2-6-2-6 2zM9 3v16M15 5v16"/></>, search: <><circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/></>, shield: <><path d="M12 3 3 7v5c0 5 9 9 9 9s9-4 9-9V7z"/><path d="m8 12 3 3 5-6"/></>, close: <path d="m6 6 12 12M18 6 6 18"/>, logout: <><path d="M9 3H4v18h5M9 12h12m-4-4 4 4-4 4"/></>, clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>, check: <path d="m5 12 4 4L19 6"/>, filter: <><path d="M4 6h16M7 12h10M10 18h4"/></> };
    return <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name] || paths.layers}</svg>;
}
function Empty({ text = 'Không tìm thấy dữ liệu', children }: {
    text?: string;
    children?: React.ReactNode;
}) { return <div className="empty"><Icon name="layers" size={32}/><h3>{text}</h3>{children}</div>; }
function Loading() { return <div className="loading" role="status" aria-label="Đang tải dữ liệu"><div className="skeleton"/><div className="skeleton"/><div className="skeleton"/></div>; }
function ErrorBox({ error, retry }: {
    error: any;
    retry?: () => void;
}) { return <div className="error" role="alert"><strong>{error.status === 401 ? 'Phiên đăng nhập đã hết hạn' : error.status === 410 ? 'Lựa chọn phiên bản đã hết hiệu lực' : error.status === 403 ? 'Bạn chưa được cấp quyền cho thao tác này' : error.status === 404 ? 'Dữ liệu không khả dụng hoặc ngoài quyền truy cập' : error.status === 413 ? 'Dữ liệu vượt giới hạn xem trước' : error.status === 429 ? 'Đã đạt giới hạn yêu cầu. Vui lòng chờ một phút.' : error.message}</strong>{error.requestId && <small>Mã yêu cầu: {error.requestId}</small>}<div>{error.status === 401 ? <a className="button" href={API + '/auth/login'}>Đăng nhập lại</a> : retry && <button onClick={retry}>Thử lại</button>}</div></div>; }
function Badge({ children, tone = 'green' }: {
    children: React.ReactNode;
    tone?: string;
}) { return <span className={'badge ' + tone}>{children}</span>; }
function App() {
    const [user, setUser] = useState<Dict | null>(null), [authReady, setAuthReady] = useState(false), [authError, setAuthError] = useState<any>(null);
    const [view, setView] = useState(new URLSearchParams(location.search).get('view') || 'overview');
    const [detail, setDetail] = useState<Dict>({ dataset: new URLSearchParams(location.search).get('dataset'), week: new URLSearchParams(location.search).get('week') });
    const [overview, setOverview] = useState<Dict | null>(null), [error, setError] = useState<any>(null), [admin, setAdmin] = useState(false), [refresh, setRefresh] = useState(0);
    useEffect(() => { const clear = () => { csrf = ''; setUser(null); setOverview(null); setAdmin(false); }; window.addEventListener('portal-session-expired', clear); return () => window.removeEventListener('portal-session-expired', clear); }, []);
    useEffect(() => { api('/session').then(u => { csrf = u.csrf_token; setUser(u); }).catch(e => { if (e.status !== 401)
        setAuthError(e); }).finally(() => setAuthReady(true)); }, []);
    useEffect(() => { if (!user)
        return; let alive = true; setError(null); api('/overview').then(o => { if (alive)
        setOverview(o); }).catch(e => { if (alive)
        setError(e); }); return () => { alive = false; }; }, [user, refresh]);
    function navigate(next: string, data: Dict = {}) { setView(next); setDetail(data); const p = new URLSearchParams({ view: next }); if (data.dataset)
        p.set('dataset', data.dataset); if (data.week)
        p.set('week', data.week); history.pushState({}, '', '/portal/?' + p); }
    useEffect(() => { const f = () => { const p = new URLSearchParams(location.search); setView(p.get('view') || 'overview'); setDetail({ dataset: p.get('dataset'), week: p.get('week') }); }; window.addEventListener('popstate', f); return () => window.removeEventListener('popstate', f); }, []);
    if (!authReady)
        return <div className="login"><Loading /></div>;
    if (!user)
        return <div className="login"><div className="login-art"><div className="brand"><span className="brand-symbol"><Icon name="layers" size={28}/></span>Climate Atlas</div><div className="login-copy"><p className="eyebrow">CLIMATE DATA OBSERVATORY</p><h1>Dữ liệu khí hậu.<br />Một góc nhìn<br /><em>rõ ràng hơn.</em></h1><p>Khám phá hành trình từ dữ liệu gốc đến những sản phẩm phân tích đáng tin cậy.</p></div><div className="orbit orbit-a"/><div className="orbit orbit-b"/><div className="orbit orbit-c"/><div className="login-foot">BRONZE · SILVER · GOLD <span>USDM / CONUS</span></div></div><div className="login-panel"><span className="eyebrow">DATA PORTAL</span><h2>Chào mừng trở lại</h2><p>Đăng nhập để khám phá và tải dữ liệu<br />trong phạm vi được cấp quyền của bạn.</p><a className="button primary login-button" href={API + '/auth/login'}><Icon name="shield"/>Đăng nhập bằng tài khoản tổ chức</a>{authError && <ErrorBox error={authError}/>}<div className="login-note"><Icon name="shield"/><span>Dữ liệu được bảo vệ theo từng nguồn và tầng.<br />Liên hệ quản trị viên nếu bạn cần thêm quyền.</span></div><small className="login-footer">Climate Atlas · USDM Data Portal</small></div></div>;
    return <div className="app"><aside className="sidebar"><button className="brand" onClick={() => navigate('overview')}><span className="brand-symbol"><Icon name="layers" size={25}/></span><span>Climate Atlas<small>DATA WORKSPACE</small></span></button><div className="nav-label">KHÁM PHÁ</div><nav><button className={view === 'overview' ? 'active' : ''} onClick={() => navigate('overview')}><Icon name="overview"/>Tổng quan</button><button className={view !== 'overview' ? 'active' : ''} onClick={() => navigate('catalog')}><Icon name="catalog"/>Danh mục dữ liệu</button></nav><div className="sidebar-note"><Icon name="shield"/><h4>Dữ liệu có thể truy vết</h4><p>Mỗi sản phẩm được liên kết với nguồn, phiên bản và kết quả kiểm định.</p></div><div className="sidebar-bottom"><span className="environment">{user.demo ? 'LOCAL DEMO' : 'DATA PORTAL'}</span><span>USDM · Hoa Kỳ</span></div></aside><div className="workspace"><header className="topbar"><div className="breadcrumbs">Workspace <span>/</span> <strong>{view === 'overview' ? 'Tổng quan' : view === 'catalog' ? 'Danh mục dữ liệu' : 'Chi tiết dataset'}</strong></div><div className="top-right">{user.demo && <Badge tone="amber">Demo localhost</Badge>}<div className="user"><span className="avatar">{user.role === 'Admin' ? 'AD' : user.role === 'Operator' ? 'OP' : 'VA'}</span><span>{user.display_name.split(' · ')[0]}<small>{user.role}</small></span></div>{user.role === 'Admin' && <button className="icon-button" title="Quản lý quyền" aria-label="Quản lý quyền" onClick={() => setAdmin(true)}><Icon name="shield"/></button>}<button className="icon-button" title="Đăng xuất" aria-label="Đăng xuất" onClick={async () => { await api('/auth/logout', { method: 'POST' }); csrf = ''; setOverview(null); setUser(null); location.assign('/portal/'); }}><Icon name="logout"/></button></div></header><main>{error ? <ErrorBox error={error} retry={() => setRefresh(n => n + 1)}/> : !overview ? <Loading /> : view === 'overview' ? <Overview data={overview} navigate={navigate}/> : view === 'catalog' ? <Catalog release={overview.release_id} navigate={navigate}/> : <DatasetDetail user={user} release={overview.release_id} initial={detail} navigate={navigate}/>}</main><footer className="page-footer"><span>Climate Atlas · Dữ liệu lịch sử USDM</span><span><Icon name="clock" size={14}/>Snapshot {overview ? new Date(overview.as_of).toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' }) : '—'} (GMT+7)</span></footer></div>{admin && <AdminPanel onClose={() => { setAdmin(false); setRefresh(n => n + 1); }} self={user}/>}</div>;
}
function Overview({ data, navigate }: {
    data: Dict;
    navigate: (v: string, d?: Dict) => void;
}) {
    const ds = data.datasets[0];
    return <><div className="page-heading"><div><p className="eyebrow">BỨC TRANH DỮ LIỆU</p><h1>Tổng quan workspace</h1><p>Dữ liệu rõ nguồn gốc. Phân tích đúng phiên bản.</p></div><button className="button" onClick={() => navigate('catalog')}><Icon name="catalog"/>Khám phá danh mục</button></div><section className="hero"><div><Badge tone="light">U.S. DROUGHT MONITOR</Badge><h2>Theo dõi hạn hán,<br />từ nguồn đến góc nhìn.</h2><p>{ds ? `${day(ds.from)} — ${day(ds.to)} · CONUS, Hoa Kỳ` : 'Chưa có dữ liệu được cấp quyền'}</p><div className="hero-meta"><span><Icon name="shield" size={17}/>Có lineage và kiểm tra chất lượng</span><span>Snapshot lịch sử</span></div></div><div className="medallion-path"><div><span className="medal bronze"><Icon name="layers" size={26}/></span><strong>Bronze</strong><small>Dữ liệu gốc</small></div><i /><div><span className="medal silver"><Icon name="layers" size={26}/></span><strong>Silver</strong><small>Chuẩn hóa</small></div><i /><div><span className="medal gold"><Icon name="layers" size={26}/></span><strong>Gold</strong><small>Sẵn sàng phân tích</small></div></div></section><div className="metrics">{[['Dataset', data.dataset_count, 'Nguồn dữ liệu được cấp quyền', 'catalog'], ['Tuần quan sát', data.week_count, 'Phạm vi lịch sử đang phục vụ', 'clock'], ['Bản ghi Gold', data.gold_rows, 'Chỉ tính build hiện hành', 'layers'], ['Geometry đã sửa', data.repairs, 'Từ kiểm tra chất lượng Silver', 'shield']].map(([title, value, desc, icon]) => <div className="metric" key={String(title)}><div><span>{title}</span><Icon name={String(icon)} size={19}/></div><strong>{value == null ? '—' : num(Number(value))}</strong><small>{desc}</small></div>)}</div><div className="overview-grid"><section className="card"><div className="card-heading"><div><h3>Phân bố mức hạn hán theo tuần</h3><p>Tỷ lệ số tâm ô lưới · không phải tỷ lệ diện tích</p></div><Badge>Gold</Badge></div>{data.series.length ? <><div className="timeline" role="img" aria-label="Biểu đồ tỷ lệ nhãn hạn hán theo tuần">{data.series.map((r: Dict) => { const total = Object.keys(colors).reduce((s, k) => s + (r[k] || 0), 0); return <div className="timeline-week" key={r.week} title={day(r.week)}>{Object.keys(colors).reverse().map(k => <span key={k} style={{ height: (r[k] / total * 100) + '%', background: colors[k] }} title={`${day(r.week)} · ${k}: ${num(r[k])}`}/>)}</div>; })}</div><div className="axis"><span>{day(data.series[0]?.week)}</span><span>{day(data.series.at(-1)?.week)}</span></div><Legend /></> : <Empty text="Chưa có quyền xem dữ liệu Gold"/>}</section><section className="card source-card"><div className="card-heading"><div><h3>Nguồn dữ liệu</h3><p>Khám phá từng sản phẩm</p></div></div>{data.datasets.length ? data.datasets.map((d: Dict) => <div key={d.dataset_id}><div className="source-heading"><span className="source-icon">US</span><div><h3>{d.display_name}</h3><p>U.S. Drought Monitor</p></div></div><div className="source-facts"><span>Không gian<strong>CONUS · EPSG:4326</strong></span><span>Tần suất<strong>Hàng tuần</strong></span><span>Phạm vi<strong>{num(d.week_count)} tuần</strong></span></div><div className="layer-chips">{d.layers.map((l: string) => <Badge key={l} tone={l}>{l}</Badge>)}</div><button className="button full" onClick={() => navigate('catalog', { dataset: d.dataset_id })}>Xem dataset</button></div>) : <Empty text="Chưa được cấp dữ liệu"/>}</section></div><div className="info-strip"><Icon name="clock"/><p><strong>Một snapshot nhất quán.</strong> Dữ liệu trong Portal là bản lịch sử đã publish. Thời điểm snapshot không phải thời điểm quan sát khí hậu.</p></div></>;
}
function Legend() { return <div className="legend">{Object.keys(colors).map(k => <span key={k}><i style={{ background: colors[k] }}/>{k === '0' ? 'Không hạn' : k}</span>)}</div>; }
function Catalog({ release, navigate }: {
    release: string;
    navigate: (v: string, d?: Dict) => void;
}) {
    const [datasets, setDatasets] = useState<Dict[]>([]), [did, setDid] = useState(''), [weeks, setWeeks] = useState<Dict | null>(null), [error, setError] = useState<any>(null), [q, setQ] = useState(''), [from, setFrom] = useState(''), [to, setTo] = useState(''), [filter, setFilter] = useState(0), [cursor, setCursor] = useState(''), [back, setBack] = useState<string[]>([]);
    useEffect(() => { let alive = true; api('/datasets?release_id=' + release + '&q=' + encodeURIComponent(q)).then(r => { if (alive) {
        setDatasets(r.items);
        setDid(r.items[0]?.dataset_id || '');
    } }).catch(setError); return () => { alive = false; }; }, [release, filter]);
    useEffect(() => { if (!did) {
        setWeeks(null);
        return;
    } ; let alive = true; setWeeks(null); setError(null); const p = new URLSearchParams({ release_id: release, limit: '12' }); if (from)
        p.set('from', from); if (to)
        p.set('to', to); if (cursor)
        p.set('cursor', cursor); api(`/datasets/${did}/weeks?${p}`).then(r => { if (alive)
        setWeeks(r); }).catch(e => { if (alive)
        setError(e); }); return () => { alive = false; }; }, [did, cursor, filter, release]);
    return <><div className="page-heading"><div><p className="eyebrow">DATA CATALOG</p><h1>Danh mục dữ liệu</h1><p>Chọn nguồn, thời gian và tầng dữ liệu bạn muốn khám phá.</p></div><Badge>{num(datasets.length)} dataset</Badge></div><form className="filters" onSubmit={e => { e.preventDefault(); setCursor(''); setBack([]); setFilter(n => n + 1); }}><label className="search"><Icon name="search"/><input aria-label="Tìm dataset" placeholder="Tìm dataset…" value={q} onChange={e => setQ(e.target.value)}/></label><label>Từ ngày<input type="date" value={from} onChange={e => setFrom(e.target.value)}/></label><label>Đến ngày<input type="date" value={to} onChange={e => setTo(e.target.value)}/></label><button className="button primary" type="submit"><Icon name="filter"/>Áp dụng</button><button className="button" type="button" onClick={() => { setQ(''); setFrom(''); setTo(''); setCursor(''); setBack([]); setFilter(n => n + 1); }}>Xóa bộ lọc</button></form>{error && <ErrorBox error={error}/>}<div className="catalog-layout"><aside className="dataset-list"><p className="eyebrow">NGUỒN DỮ LIỆU</p>{datasets.map(d => <button key={d.dataset_id} className={did === d.dataset_id ? 'selected' : ''} onClick={() => { setDid(d.dataset_id); setCursor(''); setBack([]); }}><span className="source-icon">US</span><div><strong>{d.display_name}</strong><small>{num(d.week_count)} tuần quan sát</small></div></button>)}</aside><section className="card weeks-card"><div className="card-heading"><div><h3>USDM · Dữ liệu theo tuần</h3><p>Mỗi tuần hiển thị revision hiện hành tại snapshot.</p></div><Badge tone="neutral">Historical</Badge></div>{!did ? <Empty text="Không tìm thấy dataset được cấp quyền"/> : !weeks ? <Loading /> : !weeks.items.length ? <Empty text="Không có tuần trong khoảng đã chọn"/> : <><div className="table-wrap"><table><thead><tr><th>Tuần quan sát</th><th>Tầng dữ liệu</th><th>Gold rows</th><th>Revision</th><th /></tr></thead><tbody>{weeks.items.map((w: Dict) => <tr key={w.week}><td><strong>{day(w.week)}</strong><small>USDM · CONUS</small></td><td><div className="layer-chips">{Object.entries(w.layers).map(([l, s]) => <Badge key={l} tone={s === 'available' ? l : 'neutral'}>{l}{s !== 'available' ? ' · chưa có' : ''}</Badge>)}</div></td><td>{w.gold_rows === null ? '—' : num(w.gold_rows)}</td><td>r{w.revision}</td><td><button className="text-button" onClick={() => navigate('detail', { dataset: did, week: w.week })}>Xem dữ liệu</button></td></tr>)}</tbody></table></div><Pagination back={back.length > 0} next={weeks.page.next_cursor} onBack={() => { setCursor(back.at(-1) || ''); setBack(b => b.slice(0, -1)); }} onNext={() => { setBack(b => [...b, cursor]); setCursor(weeks.page.next_cursor); }} label={`${weeks.items.length} tuần trên trang`}/></>}</section></div></>;
}
function Pagination({ back, next, onBack, onNext, label }: {
    back: boolean;
    next: any;
    onBack: () => void;
    onNext: () => void;
    label: string;
}) { return <div className="pagination"><span>{label}</span><div><button disabled={!back} onClick={onBack}>Trước</button><button disabled={!next} onClick={onNext}>Tiếp</button></div></div>; }
function DatasetDetail({ user, release, initial, navigate }: {
    user: Dict;
    release: string;
    initial: Dict;
    navigate: (v: string, d?: Dict) => void;
}) {
    const [week, setWeek] = useState(initial.week || ''), [weeks, setWeeks] = useState<Dict[]>([]), [selection, setSelection] = useState<Dict | null>(null), [layer, setLayer] = useState('gold'), [tab, setTab] = useState('Dữ liệu'), [content, setContent] = useState<Dict | null>(null), [error, setError] = useState<any>(null), [version, setVersion] = useState(''), [versions, setVersions] = useState<Dict[]>([]), [cursor, setCursor] = useState(''), [back, setBack] = useState<string[]>([]), [drought, setDrought] = useState(''), [grid, setGrid] = useState(''), [gridFilter, setGridFilter] = useState(''), [nonce, setNonce] = useState(0), [downloading, setDownloading] = useState(false), [downloadError, setDownloadError] = useState<any>(null);
    const did = initial.dataset;
    useEffect(() => { let alive = true; async function load() { let result: Dict[] = []; let next = ''; do {
        const r = await api(`/datasets/${did}/weeks?release_id=${release}&limit=100${next ? '&cursor=' + next : ''}`);
        result.push(...r.items);
        next = r.page.next_cursor;
    } while (next); if (alive)
        setWeeks(result); } load().catch(setError); return () => { alive = false; }; }, [did, release]);
    useEffect(() => { setWeek(initial.week || ''); setVersion(''); }, [initial.week]);
    useEffect(() => { if (!week || !did)
        return; let alive = true; setSelection(null); setContent(null); setError(null); setCursor(''); setBack([]); api('/selections', { method: 'POST', body: JSON.stringify({ dataset_id: did, week, release_id: release, mode: version ? 'history' : 'current', ...(version ? { version_id: version } : {}) }) }).then(r => { if (alive) {
        setSelection(r);
        setLayer(l => r.layers[l] ? l : Object.keys(r.layers)[0] || 'gold');
    } }).catch(e => { if (alive)
        setError(e); }); return () => { alive = false; }; }, [did, week, version, release, nonce]);
    useEffect(() => { if (!week)
        return; let alive = true; api(`/datasets/${did}/weeks/${week}/versions?release_id=${release}&limit=100`).then(r => { if (alive)
        setVersions(r.items); }).catch(setError); return () => { alive = false; }; }, [did, week, release, nonce]);
    useEffect(() => { setCursor(''); setBack([]); setContent(null); setDrought(''); setGrid(''); setGridFilter(''); if (layer === 'bronze' && tab === 'Bản đồ')
        setTab('Dữ liệu'); }, [layer]);
    useEffect(() => { if (!selection || tab === 'Bản đồ')
        return; let alive = true; setContent(null); setError(null); const paths: Record<string, string> = { 'Dữ liệu': 'preview', 'Schema': 'schema', 'Quality': 'quality', 'Lineage': 'lineage' }; if (tab === 'Lịch sử') {
        setContent({ items: versions });
        return;
    } let url = tab === 'Xử lý' ? `/datasets/${did}/attempts?release_id=${release}&from=${week}&to=${week}` : `/selections/${selection.selection_id}/layers/${layer}/${paths[tab]}`; if (tab === 'Dữ liệu') {
        const p = new URLSearchParams({ limit: '50' });
        if (cursor)
            p.set('cursor', cursor);
        if (drought && layer === 'gold')
            p.set('drought', drought);
        if (gridFilter && layer === 'gold')
            p.set('grid', gridFilter);
        url += '?' + p;
    } api(url).then(r => { if (alive)
        setContent(r); }).catch(e => { if (alive)
        setError(e); }); return () => { alive = false; }; }, [selection, layer, tab, cursor, drought, gridFilter, versions]);
    async function download() { setDownloadError(null); setDownloading(true); try {
        const a = selection!.layers[layer].artifacts[0];
        const r = await fetch(`${API}/selections/${selection!.selection_id}/artifacts/${a.artifact_id}/download`);
        if (r.status === 401)
            window.dispatchEvent(new Event('portal-session-expired'));
        if (!r.ok) {
            const b = await r.json();
            throw Object.assign(new Error(b.error.message), { status: r.status, requestId: b.request_id });
        }
        const blob = await r.blob();
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = r.headers.get('Content-Disposition')?.match(/filename="([^"]+)"/)?.[1] || `USDM-${week}.${a.format}`;
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 30000);
    }
    catch (e) {
        setDownloadError(e);
    }
    finally {
        setDownloading(false);
    } }
    const availability = selection?.layers[layer];
    const tabs = ['Dữ liệu', ...(layer !== 'bronze' ? ['Bản đồ'] : []), 'Schema', 'Quality', 'Lineage', 'Lịch sử', ...(user.role !== 'Viewer' ? ['Xử lý'] : [])];
    return <><button className="text-button back-link" onClick={() => navigate('catalog')}>Danh mục / USDM / CONUS</button><div className="page-heading"><div><p className="eyebrow">U.S. DROUGHT MONITOR</p><h1>USDM · CONUS</h1><p>Quan sát hạn hán theo tuần trên lục địa Hoa Kỳ.</p></div><button className="button primary" disabled={!availability?.artifacts?.[0]?.download_allowed || availability.availability !== 'available' || downloading} onClick={download}><Icon name="download"/>{downloading ? 'Đang tải…' : `Tải ${layer === 'bronze' ? 'ZIP' : layer === 'silver' ? 'GeoParquet' : 'CSV'}`}</button></div><div className="selection-bar"><label>Tuần quan sát<select value={week} onChange={e => { setSelection(null); setContent(null); setWeek(e.target.value); setVersion(''); }}>{weeks.map(w => <option key={w.week} value={w.week}>{day(w.week)}</option>)}</select></label><label>Phiên bản<select value={version} onChange={e => { setSelection(null); setContent(null); setVersion(e.target.value); }}><option value="">Hiện hành tại snapshot</option>{versions.map(v => <option key={v.version_id} value={v.version_id}>r{v.revision} · {short(v.build_id)} {v.is_current ? '(current)' : '(history)'}</option>)}</select></label><div className="selection-meta"><span>Revision <strong>{selection ? 'r' + selection.revision : '—'}</strong></span><span>Build <code>{short(selection?.build_id)}</code></span></div></div>{version && <div className="history-banner"><Icon name="clock"/>Đang xem lịch sử. Tải dữ liệu sẽ lấy đúng phiên bản này.<button onClick={() => setVersion('')}>Về current</button></div>}{downloadError && <ErrorBox error={downloadError}/>}<section className="card detail-card"><div className="layer-tabs">{selection ? ['bronze', 'silver', 'gold'].filter(l => selection.layers[l]).map(l => <button key={l} className={layer === l ? 'active ' + l : l} onClick={() => { setLayer(l); setTab('Dữ liệu'); }}><Icon name="layers"/><span>{l}<small>{l === 'bronze' ? 'Dữ liệu nguyên bản' : l === 'silver' ? 'Làm sạch & chuẩn hóa' : 'Sản phẩm phân tích'}</small></span><Badge tone={selection.layers[l].availability === 'available' ? 'green' : 'neutral'}>{selection.layers[l].availability === 'available' ? 'Sẵn sàng' : 'Chưa sẵn sàng'}</Badge></button>) : <Loading />}</div><div className="detail-tabs" role="tablist">{tabs.map(t => <button role="tab" aria-selected={tab === t} key={t} className={tab === t ? 'active' : ''} onClick={() => { setContent(null); setTab(t); setCursor(''); setBack([]); }}>{t}</button>)}</div><div className="detail-content">{error ? <ErrorBox error={error} retry={() => { setVersion(''); setNonce(n => n + 1); }}/> : !selection ? <Loading /> : availability?.availability !== 'available' ? <Empty text={availability?.availability === 'not_built' ? 'Chưa có sản phẩm cho revision này' : 'Sản phẩm không khả dụng'}><p>Portal không tự thay bằng một phiên bản cũ.</p></Empty> : tab === 'Bản đồ' ? <DataMap selection={selection} layer={layer}/> : !content ? <Loading /> : tab === 'Dữ liệu' ? <>{layer === 'gold' && <div className="table-filters"><label>Mức hạn<select value={drought} onChange={e => { setDrought(e.target.value); setCursor(''); setBack([]); }}><option value="">Tất cả</option>{Object.keys(colors).map(k => <option key={k} value={k}>{k} · {labels[k]}</option>)}</select></label><form onSubmit={e => { e.preventDefault(); setGridFilter(grid); setCursor(''); setBack([]); }}><label>Mã grid<input value={grid} onChange={e => setGrid(e.target.value)} placeholder="Ví dụ: C6"/></label><button className="button">Lọc</button></form></div>}<div className="preview-summary"><span><strong>{num(content.matched_count)}</strong> {layer === 'bronze' ? 'thành phần trong package' : 'bản ghi'} · {layer === 'bronze' ? 'Bytes đã xác minh' : 'EPSG:4326'}</span><small>{layer === 'bronze' ? 'Chưa phải kết luận chất lượng khoa học' : 'Bảng và tải xuống cùng build'}</small></div><DataTable columns={content.columns || []} rows={content.rows || []}/><Pagination label="50 dòng/trang" back={back.length > 0} next={content.page?.next_cursor} onBack={() => { setCursor(back.at(-1) || ''); setBack(b => b.slice(0, -1)); }} onNext={() => { setBack(b => [...b, cursor]); setCursor(content.page.next_cursor); }}/>{layer === 'gold' && <Legend />}</> : tab === 'Schema' ? <><div className="preview-summary">{content.crs ? `Hệ tọa độ: ${content.crs}` : 'Schema gói dữ liệu Bronze'}</div><DataTable columns={['name', 'type', 'nullable', 'unit', 'description'].map(name => ({ name }))} rows={content.fields || []}/></> : tab === 'Quality' ? <Quality metrics={content.metrics}/> : tab === 'Lineage' ? <Lineage data={content}/> : tab === 'Lịch sử' ? <div className="table-wrap"><table><thead><tr><th>Revision</th><th>Build</th><th>Hoàn tất</th><th>Trạng thái</th><th /></tr></thead><tbody>{versions.map(v => <tr key={v.version_id}><td>r{v.revision}</td><td><code>{short(v.build_id)}</code></td><td>{day(v.completed_at)}</td><td><Badge tone={v.is_current ? 'green' : 'neutral'}>{v.is_current ? 'Current' : 'History'}</Badge></td><td><button className="text-button" onClick={() => { setVersion(v.version_id); setTab('Dữ liệu'); }}>Xem phiên bản</button></td></tr>)}</tbody></table></div> : <><div className="info-strip">Lịch sử tại snapshot; không phải trạng thái đang chạy.</div><DataTable columns={['date', 'status', 'created_at', 'safe_reason'].map(name => ({ name }))} rows={content.items || []}/></>}</div></section></>;
}
function DataTable({ columns, rows }: {
    columns: Dict[];
    rows: Dict[];
}) { if (!rows.length)
    return <Empty text="Không có bản ghi phù hợp"/>; return <div className="table-wrap"><table><thead><tr>{columns.map(c => <th key={c.name}>{c.name}</th>)}</tr></thead><tbody>{rows.map((r, i) => <tr key={r.grid || r.row_id || r.name || i}>{columns.map(c => <td key={c.name}>{c.name === 'drought' || c.name === 'drought_category' ? <span className="drought-label" style={{ background: colors[r[c.name]] + '30', color: r[c.name] === '0' ? '#355e55' : colors[r[c.name]] }}>{r[c.name]}</span> : r[c.name] === null || r[c.name] === undefined ? '—' : typeof r[c.name] === 'boolean' ? (r[c.name] ? 'Có' : 'Không') : c.name === 'sha256' ? <code title={r[c.name]}>{short(r[c.name])}</code> : String(r[c.name])}</td>)}</tr>)}</tbody></table></div>; }
function Quality({ metrics }: {
    metrics: Dict;
}) { return <><div className="quality-heading"><span className="quality-icon"><Icon name="shield" size={30}/></span><div><h3>Kết quả kiểm tra chất lượng</h3><p>Được ghi nhận từ sản phẩm đã publish, không suy diễn từ giao diện.</p></div></div><div className="quality-grid">{Object.entries(metrics || {}).filter(([, v]) => typeof v !== 'object').map(([k, v]) => <div key={k}><span>{k.replaceAll('_', ' ')}</span><strong title={String(v)}>{typeof v === 'number' ? num(v) : typeof v === 'boolean' ? (v ? 'Có' : 'Không') : String(v).length > 60 ? short(String(v)) : String(v)}</strong></div>)}</div>{metrics?.counts && <div className="quality-counts"><h4>Số tâm grid theo nhãn</h4><Legend />{Object.entries(metrics.counts).map(([k, v]) => <div key={k}><span>{k} · {labels[k]}</span><strong>{num(Number(v))}</strong></div>)}</div>}</>; }
function Lineage({ data }: {
    data: Dict;
}) { return <><h3>Hành trình của dữ liệu</h3><p className="muted">Mỗi sản phẩm liên kết với input và recipe của cùng build.</p><div className="lineage">{(data.nodes || []).map((n: Dict) => <div key={n.layer} className={'lineage-node ' + n.layer}><Icon name="layers" size={26}/><h3>{n.layer}</h3>{n.restricted ? <p>Nguồn phụ thuộc bị giới hạn</p> : <><small>ID</small><code title={n.id}>{short(n.id)}</code><small>SHA-256</small><code title={n.sha256}>{short(n.sha256)}</code></>}</div>)}</div>{data.recipe && <div className="recipe"><h4>Recipe & thư viện</h4><div>{Object.entries(data.recipe.libraries || {}).map(([k, v]) => <Badge key={k} tone="neutral">{k} {String(v)}</Badge>)}</div><p><code>Grid reference: {short(data.recipe.grid)}</code></p></div>}</>; }
function DataMap({ selection, layer }: {
    selection: Dict;
    layer: string;
}) {
    const el = useRef<HTMLDivElement>(null), map = useRef<maplibregl.Map | null>(null), [error, setError] = useState<any>(null), [busy, setBusy] = useState(true), [meta, setMeta] = useState<Dict | null>(null), [drought, setDrought] = useState('');
    useEffect(() => { if (!el.current)
        return; const m = new maplibregl.Map({ container: el.current, center: [-97, 38], zoom: 3, minZoom: 2, maxZoom: 10, style: { version: 8, sources: {}, layers: [{ id: 'background', type: 'background', paint: { 'background-color': '#edf2f0' } }] }, attributionControl: false }); map.current = m; m.addControl(new maplibregl.NavigationControl(), 'top-right'); const grid: Dict = { type: 'FeatureCollection', features: [] }; for (let lon = -130; lon <= -60; lon += 5)
        grid.features.push({ type: 'Feature', geometry: { type: 'LineString', coordinates: [[lon, 20], [lon, 55]] }, properties: {} }); for (let lat = 20; lat <= 55; lat += 5)
        grid.features.push({ type: 'Feature', geometry: { type: 'LineString', coordinates: [[-130, lat], [-60, lat]] }, properties: {} }); m.on('load', () => { m.addSource('graticule', { type: 'geojson', data: grid as any }); m.addLayer({ id: 'graticule', type: 'line', source: 'graticule', paint: { 'line-color': '#d2dfda', 'line-width': 1 } }); m.addSource('usdm', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } }); const expression: any = ['match', ['get', 'drought'], ...Object.entries(colors).flat(), '#aaa']; m.addLayer(layer === 'silver' ? { id: 'data', type: 'fill', source: 'usdm', paint: { 'fill-color': expression, 'fill-opacity': 0.82, 'fill-outline-color': '#ffffff' } } : { id: 'data', type: 'circle', source: 'usdm', paint: { 'circle-color': expression, 'circle-radius': ['interpolate', ['linear'], ['zoom'], 2, 2, 6, 7], 'circle-stroke-width': 0.5, 'circle-stroke-color': '#ffffff' } }); m.on('click', 'data', e => { const f = e.features?.[0]; if (!f)
        return; const box = document.createElement('div'); box.className = 'map-tooltip'; const strong = document.createElement('strong'); strong.textContent = f.properties?.drought + ' · ' + labels[f.properties?.drought]; const text = document.createElement('p'); text.textContent = (f.properties?.grid ? 'Grid ' + f.properties.grid : 'Polygon ' + f.id) + ' · ' + day(selection.week); box.append(strong, text); new maplibregl.Popup().setLngLat(e.lngLat).setDOMContent(box).addTo(m); }); m.on('mouseenter', 'data', () => { m.getCanvas().style.cursor = 'pointer'; }); m.on('mouseleave', 'data', () => { m.getCanvas().style.cursor = ''; }); m.fire('portal-ready' as any); }); return () => { m.remove(); map.current = null; }; }, [selection.selection_id, layer]);
    useEffect(() => { const m = map.current!; if (!m)
        return; let alive = true, seq = 0; let timer: ReturnType<typeof setTimeout>; async function load() { const id = ++seq; setBusy(true); setError(null); const b = m.getBounds(); if (!b)
        return; const p = new URLSearchParams({ bbox: `${Math.max(-180, b.getWest())},${Math.max(-90, b.getSouth())},${Math.min(180, b.getEast())},${Math.min(90, b.getNorth())}`, zoom: String(Math.round(m.getZoom())) }); if (drought)
        p.set('drought', drought); try {
        const r = await api(`/selections/${selection.selection_id}/layers/${layer}/map?${p}`);
        if (alive && seq === id) {
            (m.getSource('usdm') as maplibregl.GeoJSONSource)?.setData(r);
            setMeta(r.metadata);
            m.once('idle', () => { if (el.current)
                el.current.dataset.renderedFeatures = String(m.queryRenderedFeatures({ layers: ['data'] }).length); });
        }
    }
    catch (e) {
        if (alive && seq === id)
            setError(e);
    }
    finally {
        if (alive && seq === id)
            setBusy(false);
    } } const schedule = () => { clearTimeout(timer); timer = setTimeout(load, 300); }; m.on('portal-ready' as any, schedule); m.on('moveend', schedule); if (m.getSource('usdm'))
        schedule(); return () => { alive = false; clearTimeout(timer); m.off('portal-ready' as any, schedule); m.off('moveend', schedule); }; }, [selection.selection_id, layer, drought]);
    return <div className="map-section"><div className="map-toolbar"><div><h3>{layer === 'silver' ? 'Đa giác hạn hán' : 'Tâm ô lưới hạn hán'}</h3><span className="muted">{day(selection.week)} · EPSG:4326 · USDM</span></div><label>Mức hạn<select value={drought} onChange={e => setDrought(e.target.value)}><option value="">Tất cả</option>{Object.keys(colors).filter(k => layer === 'gold' || k !== '0').map(k => <option value={k} key={k}>{k} · {labels[k]}</option>)}</select></label></div>{error && <ErrorBox error={error}/>}<div className="map-container" ref={el} aria-label="Bản đồ hạn hán USDM"/>{busy && <span className="map-loading" role="status">Đang tải lớp dữ liệu…</span>}<div className="map-caption"><Legend /><small>{meta ? `${num(meta.feature_count)} đối tượng · ` : ''}{layer === 'silver' ? 'Geometry đã rút gọn để hiển thị. Tải Parquet để lấy bản đầy đủ.' : 'Hiển thị tâm grid, không phải diện tích hạn hán.'}</small></div></div>;
}
function AdminPanel({ onClose, self }: {
    onClose: () => void;
    self: Dict;
}) {
    const [users, setUsers] = useState<Dict[]>([]), [datasets, setDatasets] = useState<Dict[]>([]), [target, setTarget] = useState(''), [grants, setGrants] = useState<Dict[]>([]), [draft, setDraft] = useState<Record<string, string[]>>({}), [role, setRole] = useState('Viewer'), [enabled, setEnabled] = useState(true), [error, setError] = useState<any>(null), [message, setMessage] = useState(''), [saving, setSaving] = useState(false);
    function reload() { Promise.all([api('/admin/users?limit=100'), api('/admin/datasets?limit=100')]).then(([u, d]) => { setUsers(u.items); setDatasets(d.items); setTarget(t => t || u.items[0]?.user_id || ''); }).catch(setError); }
    useEffect(reload, []);
    useEffect(() => { if (!target)
        return; setMessage(''); setError(null); const user = users.find(u => u.user_id === target); setRole(user?.role || 'Viewer'); setEnabled(Boolean(user?.enabled)); api(`/admin/users/${target}/grants?limit=100`).then(r => { setGrants(r.items); setDraft(Object.fromEntries(r.items.map((g: Dict) => [g.dataset_id + ':' + g.layer, g.actions]))); }).catch(setError); }, [target, users]);
    async function save() { setSaving(true); setError(null); setMessage(''); try {
        const u = users.find(u => u.user_id === target)!;
        if (u.role !== role || Boolean(u.enabled) !== enabled)
            await api(`/admin/users/${target}`, { method: 'PATCH', headers: { 'If-Match': String(u.version) }, body: JSON.stringify({ role, enabled }) });
        for (const ds of datasets) {
            for (const layer of ['bronze', 'silver', 'gold']) {
                const actions = draft[ds.dataset_id + ':' + layer] || [];
                const old = grants.find(g => g.dataset_id === ds.dataset_id && g.layer === layer);
                if (JSON.stringify([...(old?.actions || [])].sort()) === JSON.stringify([...actions].sort()))
                    continue;
                const url = `/admin/users/${target}/grants/${ds.dataset_id}/${layer}`;
                if (!actions.length && old)
                    await api(url, { method: 'DELETE', headers: { 'If-Match': String(old.version) } });
                else if (actions.length)
                    await api(url, { method: 'PUT', headers: old ? { 'If-Match': String(old.version) } : { 'If-None-Match': '*' }, body: JSON.stringify({ actions }) });
            }
        }
        const fresh = await api(`/admin/users/${target}/grants?limit=100`);
        setGrants(fresh.items);
        setMessage('Đã lưu quyền. Có hiệu lực từ yêu cầu kế tiếp.');
        const list = await api('/admin/users?limit=100');
        setUsers(list.items);
    }
    catch (e) {
        setError(e);
    }
    finally {
        setSaving(false);
    } }
    return <div className="modal-backdrop" onClick={onClose}><section className="admin-drawer" role="dialog" aria-modal="true" aria-label="Quản lý quyền" onClick={e => e.stopPropagation()}><div className="drawer-heading"><div><p className="eyebrow">ADMINISTRATION</p><h2>Quản lý quyền</h2></div><button className="icon-button" aria-label="Đóng" onClick={onClose}><Icon name="close"/></button></div><p className="muted">Cấp quyền rõ ràng theo dataset và từng tầng dữ liệu.</p><label>Người dùng<select value={target} onChange={e => setTarget(e.target.value)}>{users.map(u => <option value={u.user_id} key={u.user_id}>{u.display_name}</option>)}</select></label><div className="admin-role"><label>Vai trò<select value={role} disabled={target === self.user_id} onChange={e => setRole(e.target.value)}>{['Viewer', 'Operator', 'Admin'].map(r => <option key={r}>{r}</option>)}</select></label><label className="checkbox"><input type="checkbox" checked={enabled} disabled={target === self.user_id} onChange={e => setEnabled(e.target.checked)}/>Hoạt động</label></div>{datasets.map(d => <div className="grant-card" key={d.dataset_id}><h3>{d.display_name}</h3><table><thead><tr><th>Layer</th><th>Read</th><th>Download</th></tr></thead><tbody>{['bronze', 'silver', 'gold'].map(layer => { const key = d.dataset_id + ':' + layer; const actions = draft[key] || []; return <tr key={layer}><td>{layer}</td>{['read', 'download'].map(action => <td key={action}><input type="checkbox" aria-label={layer + ' ' + action} checked={actions.includes(action)} disabled={action === 'download' && !actions.includes('read')} onChange={e => setDraft(old => ({ ...old, [key]: action === 'read' ? (e.target.checked ? ['read'] : []) : (e.target.checked ? ['read', 'download'] : ['read']) }))}/></td>)}</tr>; })}</tbody></table></div>)}{error && <ErrorBox error={error}/>} {message && <div className="success" role="status">{message}</div>}<div className="drawer-actions"><button className="button" onClick={onClose}>Đóng</button><button className="button primary" disabled={saving || !target} onClick={save}>{saving ? 'Đang lưu…' : 'Lưu thay đổi'}</button></div></section></div>;
}
createRoot(document.getElementById('root')!).render(<App />);
