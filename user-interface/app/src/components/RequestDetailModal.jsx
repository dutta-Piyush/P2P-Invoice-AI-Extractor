import { useEffect, useRef, useState } from "react";
import { updateRequestStatus } from "../data/api";
import { COMMODITY_GROUPS, fmt } from "../utils/procurementUtils";

const STATUS_LABEL = {
  open: "Open",
  in_progress: "In Progress",
  closed: "Closed",
  cancelled: "Cancelled",
  rejected: "Rejected",
};

const STATUS_OPTIONS = [
  { value: "open", label: "Open" },
  { value: "in_progress", label: "In Progress" },
  { value: "closed", label: "Closed" },
  { value: "cancelled", label: "Cancelled" },
  { value: "rejected", label: "Rejected" },
];

export default function RequestDetailModal({ request, onClose, onUpdated }) {
  const [selectedStatus, setSelectedStatus] = useState(request.status);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const overlayRef = useRef(null);

  // Close on Escape key
  useEffect(() => {
    const handler = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const handleSave = async () => {
    setSaving(true);
    setSaveError("");
    try {
      const updated = await updateRequestStatus(
        request.id,
        selectedStatus,
        note,
      );
      setNote("");
      onUpdated(updated);
    } catch (err) {
      setSaveError(err.message || "Failed to update status. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  const hasChanges =
    selectedStatus !== request.status || note.trim().length > 0;

  return (
    <div
      className="modal-overlay"
      ref={overlayRef}
      onClick={(e) => {
        if (e.target === overlayRef.current) onClose();
      }}
    >
      <div className="modal">
        <div className="modal-header">
          <div className="modal-header-left">
            <span className="modal-id">{request.id}</span>
            <h2 className="modal-title">{request.title}</h2>
          </div>
          <button
            className="modal-close-btn"
            onClick={onClose}
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="modal-body">
          {/* Request details */}
          <section className="modal-section">
            <h3>Request details</h3>
            <div className="modal-detail-grid">
              <div className="modal-detail-item">
                <span className="modal-detail-label">Requestor</span>
                <span className="modal-detail-value">
                  {request.requestor_name}
                </span>
              </div>
              <div className="modal-detail-item">
                <span className="modal-detail-label">Department</span>
                <span className="modal-detail-value">{request.department}</span>
              </div>
              <div className="modal-detail-item">
                <span className="modal-detail-label">Vendor</span>
                <span className="modal-detail-value">
                  {request.vendor_name}
                </span>
              </div>
              <div className="modal-detail-item">
                <span className="modal-detail-label">VAT ID</span>
                <span className="modal-detail-value">{request.vat_id}</span>
              </div>
              <div className="modal-detail-item">
                <span className="modal-detail-label">Commodity</span>
                <span className="modal-detail-value">
                  {request.commodity_group_id} —{" "}
                  {COMMODITY_GROUPS[request.commodity_group_id] ?? "Unknown"}
                </span>
              </div>
              <div className="modal-detail-item">
                <span className="modal-detail-label">Total cost</span>
                <span className="modal-detail-value">
                  {fmt(request.total_cost)}
                </span>
              </div>
            </div>
          </section>

          {/* Order lines */}
          <section className="modal-section">
            <h3>Order lines</h3>
            <table className="modal-lines-table">
              <thead>
                <tr>
                  <th>Description</th>
                  <th>Unit price</th>
                  <th>Qty</th>
                  <th>Unit</th>
                  <th>Discount %</th>
                  <th>Total</th>
                </tr>
              </thead>
              <tbody>
                {request.order_lines.map((line, i) => (
                  <tr key={i}>
                    <td>{line.position_description}</td>
                    <td>{fmt(line.unit_price)}</td>
                    <td>{line.amount}</td>
                    <td>{line.unit}</td>
                    <td>{line.discount > 0 ? `${line.discount}%` : "—"}</td>
                    <td>{fmt(line.total_price)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          {/* Status update */}
          <section className="modal-section">
            <h3>Update status</h3>
            <div className="modal-status-row">
              <select
                value={selectedStatus}
                onChange={(e) => setSelectedStatus(e.target.value)}
                className="modal-status-select"
              >
                {STATUS_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <input
                className="modal-note-input"
                placeholder="Add a note (optional)"
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
              <button
                className="modal-save-btn"
                onClick={handleSave}
                disabled={saving || !hasChanges}
              >
                {saving ? "Saving…" : "Save"}
              </button>
            </div>
            {saveError && <div className="modal-save-error">{saveError}</div>}
          </section>

          {/* Status history */}
          <section className="modal-section">
            <h3>Status history</h3>
            <ol className="timeline">
              {[...request.status_history].reverse().map((event, i) => (
                <li key={i} className="timeline-event">
                  <div className="timeline-dot" />
                  <div className="timeline-content">
                    <span className="timeline-status">
                      {STATUS_LABEL[event.to_status] ?? event.to_status}
                    </span>
                    {event.from_status && (
                      <span className="timeline-from">
                        {" "}
                        (from{" "}
                        {STATUS_LABEL[event.from_status] ?? event.from_status})
                      </span>
                    )}
                    <div className="timeline-meta">{event.at}</div>
                    {event.note && (
                      <div className="timeline-note">"{event.note}"</div>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          </section>
        </div>
      </div>
    </div>
  );
}
