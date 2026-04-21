import { Save, X } from "lucide-react";
import { useEffect, useState } from "react";
import type { Cell, MasterData } from "../api/client";

type Props = {
  cell: Cell | null;
  masters: MasterData | null;
  onClose: () => void;
  onSave: (payload: { subject_id: number | null; teacher_id: number | null; notes: string }) => void;
};

export function EditModal({ cell, masters, onClose, onSave }: Props) {
  const [subjectId, setSubjectId] = useState<number | null>(cell?.subject_id ?? null);
  const [teacherId, setTeacherId] = useState<number | null>(cell?.teacher_id ?? null);
  const [notes, setNotes] = useState(cell?.notes ?? "");
  useEffect(() => {
    setSubjectId(cell?.subject_id ?? null);
    setTeacherId(cell?.teacher_id ?? null);
    setNotes(cell?.notes ?? "");
  }, [cell]);
  if (!cell || !masters) return null;
  return (
    <div className="modalBackdrop">
      <div className="modal">
        <div className="modalHeader">
          <h3>{cell.day} · Period {cell.period_number}</h3>
          <button className="iconButton" onClick={onClose} title="Close"><X size={18} /></button>
        </div>
        <label>Subject</label>
        <select value={subjectId ?? ""} onChange={(event) => setSubjectId(event.target.value ? Number(event.target.value) : null)}>
          <option value="">Open / break</option>
          {masters.subjects.map((subject) => <option value={subject.id} key={subject.id}>{subject.code} · {subject.name}</option>)}
        </select>
        <label>Teacher</label>
        <select value={teacherId ?? ""} onChange={(event) => setTeacherId(event.target.value ? Number(event.target.value) : null)}>
          <option value="">No teacher</option>
          {masters.teachers.map((teacher) => <option value={teacher.id} key={teacher.id}>{teacher.name}</option>)}
        </select>
        <label>Notes</label>
        <input value={notes} onChange={(event) => setNotes(event.target.value)} />
        <div className="modalActions">
          <button onClick={() => onSave({ subject_id: subjectId, teacher_id: teacherId, notes })}><Save size={16} /> Save</button>
        </div>
      </div>
    </div>
  );
}
