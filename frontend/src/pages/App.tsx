import { Activity, CalendarDays, Download, FileSpreadsheet, LogOut, Play, ShieldCheck, Upload, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, AuthError, type AdminOverview, type Cell, type Constraint, type MasterData, type Timetable, type UserProfile } from "../api/client";
import { EditModal } from "../components/EditModal";
import { TimetableGrid } from "../components/TimetableGrid";

export function App() {
  const [auth, setAuth] = useState(() => localStorage.getItem("token"));
  const [mode, setMode] = useState<"login" | "register">("login");
  const [form, setForm] = useState({ school_name: "", full_name: "", email: "", password: "" });
  const [summary, setSummary] = useState<Record<string, number>>({});
  const [masters, setMasters] = useState<MasterData | null>(null);
  const [rulesText, setRulesText] = useState("");
  const [previewRules, setPreviewRules] = useState<Constraint[]>([]);
  const [timetable, setTimetable] = useState<Timetable | null>(null);
  const [selectedSection, setSelectedSection] = useState<number | null>(null);
  const [selectedTeacher, setSelectedTeacher] = useState<number | null>(null);
  const [timetables, setTimetables] = useState<{ id: number; name: string; status: string }[]>([]);
  const [editing, setEditing] = useState<Cell | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [adminOverview, setAdminOverview] = useState<AdminOverview | null>(null);
  const [message, setMessage] = useState("");

  async function refresh() {
    if (!localStorage.getItem("token")) return;
    try {
      const me = await api.me();
      setProfile(me);
      if (me.role === "superadmin") {
        setAdminOverview(await api.adminOverview());
        return;
      }
      const [s, m, ts] = await Promise.all([api.summary(), api.masters(), api.timetables()]);
      setSummary(s);
      setMasters(m);
      setTimetables(ts);
      if (!selectedSection && m.sections[0]) setSelectedSection(m.sections[0].id);
    } catch (error) {
      if (error instanceof AuthError) {
        localStorage.removeItem("token");
        setAuth(null);
        setMessage("Session expired. Please log in again.");
        return;
      }
      throw error;
    }
  }

  useEffect(() => { refresh().catch((error) => setMessage(error.message)); }, [auth]);

  const filteredTimetable = useMemo(() => timetable, [timetable]);

  async function submitAuth() {
    if (!form.email || !form.password || (mode === "register" && (!form.school_name || !form.full_name))) {
      setMessage("Please fill all required fields.");
      return;
    }
    const result = mode === "register" ? await api.register(form) : await api.login({ email: form.email, password: form.password });
    localStorage.setItem("token", result.access_token);
    setAuth(result.access_token);
    setProfile(null);
    setAdminOverview(null);
    setMessage(`Signed in to ${result.school_name}`);
  }

  async function upload(file: File | null) {
    if (!file) return;
    const result = await api.upload(file);
    setMessage(result.errors.length ? `${result.errors.length} validation errors found` : "Excel data imported successfully");
    await refresh();
  }

  async function downloadTemplate() {
    await api.downloadTemplate();
    setMessage("Template downloaded");
  }

  async function parseRules() {
    const result = await api.parseRules(rulesText);
    setPreviewRules(result.constraints);
    setMessage(`Parsed by ${result.provider}`);
  }

  async function approveRules() {
    await Promise.all(previewRules.map((rule) => api.saveRule(rule)));
    setPreviewRules([]);
    setMessage("Rules saved");
  }

  async function generate() {
    const result = await api.generate(`Weekly Timetable ${new Date().toLocaleString()}`);
    setTimetable(result);
    setMessage(result.conflicts.length ? `Generated with ${result.conflicts.length} conflicts to review` : "Timetable generated successfully");
    await refresh();
  }

  async function exportTimetable() {
    if (!timetable) return;
    await api.exportTimetable(timetable.timetable_id);
    setMessage("Timetable export downloaded");
  }

  async function loadTimetable(id: number) {
    const result = await api.timetable(id, selectedTeacher ? undefined : selectedSection ?? undefined, selectedTeacher ?? undefined);
    setTimetable(result);
  }

  async function saveEdit(payload: { subject_id: number | null; teacher_id: number | null; notes: string }) {
    if (!timetable || !editing) return;
    const conflicts = await api.editEntry(timetable.timetable_id, { section_id: editing.section_id, day: editing.day, period_number: editing.period_number, ...payload });
    if (conflicts.length) {
      setMessage(conflicts.map((conflict) => conflict.message).join("; "));
      return;
    }
    setEditing(null);
    await loadTimetable(timetable.timetable_id);
    setMessage("Manual edit saved and validated");
  }

  if (!auth) {
    return (
      <main className="authPage">
        <section className="authPanel">
          <h1>Smart Timetable Generator</h1>
          <p>Excel-driven school scheduling with rule parsing and conflict-aware manual editing.</p>
          <div className="segmented">
            <button className={mode === "login" ? "active" : ""} onClick={() => setMode("login")}>Login</button>
            <button className={mode === "register" ? "active" : ""} onClick={() => setMode("register")}>Register</button>
          </div>
          {mode === "register" && <input value={form.school_name} onChange={(e) => setForm({ ...form, school_name: e.target.value })} placeholder="School name" />}
          {mode === "register" && <input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} placeholder="Full name" />}
          <input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="Email" />
          <input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="Password" />
          <button onClick={submitAuth}><ShieldCheck size={16} /> Continue</button>
          {message && <p className="notice">{message}</p>}
        </section>
      </main>
    );
  }

  return (
    <div className="shell">
      <aside>
        <h2>Smart Timetable</h2>
        <nav>
          {profile?.role === "superadmin" ? (
            <a href="#admin"><Users size={17} /> Platform Admin</a>
          ) : (
            <>
              <a href="#data"><FileSpreadsheet size={17} /> Data</a>
              <a href="#rules"><ShieldCheck size={17} /> Rules</a>
              <a href="#generate"><CalendarDays size={17} /> Timetable</a>
            </>
          )}
        </nav>
        <button className="ghost" onClick={() => { localStorage.removeItem("token"); setAuth(null); setProfile(null); setAdminOverview(null); }}><LogOut size={16} /> Logout</button>
      </aside>
      <main>
        <header>
          <div>
            <h1>School timetable workspace</h1>
            <p>Import, generate, review conflicts, and manually adjust the weekly timetable.</p>
          </div>
          {message && <div className="banner">{message}</div>}
        </header>

        {profile?.role === "superadmin" ? (
          <section id="admin" className="band">
            <div className="sectionHeader">
              <h2>Platform Admin</h2>
              <button onClick={() => refresh()}><Activity size={16} /> Refresh</button>
            </div>
            <div className="stats">
              {adminOverview && Object.entries(adminOverview.stats).map(([key, value]) => <div key={key}><strong>{value}</strong><span>{key.replaceAll("_", " ")}</span></div>)}
            </div>
            <div className="adminColumns">
              <div>
                <h3>Registered Schools</h3>
                <table className="adminTable">
                  <thead><tr><th>School</th><th>Users</th><th>Uploads</th><th>Timetables</th></tr></thead>
                  <tbody>{adminOverview?.schools.map((school) => <tr key={school.id}><td>{school.name}</td><td>{school.users}</td><td>{school.uploads}</td><td>{school.timetables}</td></tr>)}</tbody>
                </table>
              </div>
              <div>
                <h3>Users</h3>
                <table className="adminTable">
                  <thead><tr><th>User</th><th>School</th><th>Role</th></tr></thead>
                  <tbody>{adminOverview?.users.map((user) => <tr key={user.id}><td>{user.email}<br /><span>{user.full_name}</span></td><td>{user.school_name}</td><td>{user.role}</td></tr>)}</tbody>
                </table>
              </div>
            </div>
            <h3>Recent Website Activity</h3>
            <table className="adminTable">
              <thead><tr><th>When</th><th>School</th><th>User</th><th>Action</th><th>Detail</th></tr></thead>
              <tbody>
                {adminOverview?.activity.map((item) => (
                  <tr key={item.id}>
                    <td>{new Date(item.created_at).toLocaleString()}</td>
                    <td>{item.school_name || "-"}</td>
                    <td>{item.user_email || "-"}</td>
                    <td>{item.action.replaceAll("_", " ")}</td>
                    <td><code>{item.detail}</code></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        ) : (
          <>

        <section id="data" className="band">
          <div className="sectionHeader">
            <h2>Excel Data</h2>
            <button onClick={downloadTemplate}><Download size={16} /> Template</button>
          </div>
          <label className="uploadBox">
            <Upload size={20} />
            <span>Upload completed Excel workbook</span>
            <input type="file" accept=".xlsx" onChange={(event) => upload(event.target.files?.[0] ?? null)} />
          </label>
          <div className="stats">{Object.entries(summary).map(([key, value]) => <div key={key}><strong>{value}</strong><span>{key.replaceAll("_", " ")}</span></div>)}</div>
        </section>

        <section id="rules" className="band">
          <div className="sectionHeader"><h2>Natural-Language Rules</h2><button onClick={parseRules}><ShieldCheck size={16} /> Parse</button></div>
          <textarea value={rulesText} onChange={(event) => setRulesText(event.target.value)} placeholder="Example: Teacher Ravi is unavailable on Wednesday period 4. Keep Math in first half for Class 5A." />
          {previewRules.length > 0 && (
            <div className="rulePreview">
              {previewRules.map((rule, index) => <div key={index}><strong>{rule.rule_type}</strong><span>{rule.priority} · {(rule.confidence_score * 100).toFixed(0)}%</span><p>{rule.parsed_description}</p></div>)}
              <button onClick={approveRules}>Approve rules</button>
            </div>
          )}
        </section>

        <section id="generate" className="band">
          <div className="sectionHeader">
            <h2>Timetable</h2>
            <div className="actions">
              <select onChange={(event) => loadTimetable(Number(event.target.value))} defaultValue="">
                <option value="" disabled>Select timetable</option>
                {timetables.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.status}</option>)}
              </select>
              <button onClick={generate}><Play size={16} /> Generate</button>
              {timetable && <button onClick={exportTimetable}><Download size={16} /> Export</button>}
            </div>
          </div>
          <div className="filters">
            <select value={selectedSection ?? ""} onChange={(event) => { setSelectedSection(Number(event.target.value)); setSelectedTeacher(null); }}>
              {masters?.sections.map((section) => <option key={section.id} value={section.id}>{section.display_name}</option>)}
            </select>
            <select value={selectedTeacher ?? ""} onChange={(event) => { setSelectedTeacher(event.target.value ? Number(event.target.value) : null); }}>
              <option value="">Class view</option>
              {masters?.teachers.map((teacher) => <option key={teacher.id} value={teacher.id}>{teacher.name}</option>)}
            </select>
            {timetable && <button className="ghost" onClick={() => loadTimetable(timetable.timetable_id)}>Apply filter</button>}
          </div>
          {filteredTimetable?.conflicts.length ? <div className="conflicts">{filteredTimetable.conflicts.slice(0, 5).map((c, i) => <p key={i}>{c.message}</p>)}</div> : null}
          <TimetableGrid timetable={filteredTimetable} sectionId={selectedTeacher ? null : selectedSection} onEdit={setEditing} />
        </section>
          </>
        )}
      </main>
      <EditModal cell={editing} masters={masters} onClose={() => setEditing(null)} onSave={saveEdit} />
    </div>
  );
}
