import { Edit3 } from "lucide-react";
import type { Cell, Timetable } from "../api/client";

type Props = {
  timetable: Timetable | null;
  sectionId: number | null;
  onEdit: (cell: Cell) => void;
};

export function TimetableGrid({ timetable, sectionId, onEdit }: Props) {
  if (!timetable) return <div className="empty">Generate or select a timetable to view the weekly grid.</div>;
  const entries = timetable.entries.filter((entry) => !sectionId || entry.section_id === sectionId);
  return (
    <div className="gridWrap">
      <table className="timetable">
        <thead>
          <tr>
            <th>Day</th>
            {timetable.periods.map((period) => <th key={period}>P{period}</th>)}
          </tr>
        </thead>
        <tbody>
          {timetable.days.map((day) => (
            <tr key={day}>
              <td className="dayCell">{day}</td>
              {timetable.periods.map((period) => {
                const cell = entries.find((item) => item.day === day && item.period_number === period);
                return (
                  <td key={`${day}-${period}`} className={cell?.is_break ? "breakCell" : cell?.notes === "Unfilled" ? "warnCell" : ""}>
                    {cell ? (
                      <button className="cellButton" onClick={() => onEdit(cell)} title="Edit timetable slot">
                        <span className="subject">{cell.is_break ? "Break" : cell.subject_code || "Open"}</span>
                        <span className="teacher">{cell.teacher_name || cell.notes}</span>
                        {!cell.is_break && <Edit3 size={14} />}
                      </button>
                    ) : (
                      <span className="muted">-</span>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
