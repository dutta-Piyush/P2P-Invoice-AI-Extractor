import { useEffect, useState } from "react";
import { getRequests } from "../data/api";
import { fmt } from "../utils/procurementUtils";
import RequestDetailModal from "./RequestDetailModal";

const STATUS_LABEL = {
  open: "Open",
  in_progress: "In Progress",
  closed: "Closed",
  cancelled: "Cancelled",
  rejected: "Rejected",
};

export default function RequestOverview({ refreshKey, onNotice }) {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedRequest, setSelectedRequest] = useState(null);

  const loadRequests = async () => {
    setLoading(true);
    try {
      const data = await getRequests();
      setRequests(data);
    } catch {
      onNotice("Failed to load requests.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRequests();
  }, [refreshKey]);

  const handleUpdated = (updated) => {
    setRequests((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
    setSelectedRequest(updated);
  };

  if (loading) {
    return <div className="card">Loading requests…</div>;
  }

  if (requests.length === 0) {
    return <div className="card">No requests found. Create one from New request.</div>;
  }

  return (
    <>
      {selectedRequest && (
        <RequestDetailModal
          request={selectedRequest}
          onClose={() => setSelectedRequest(null)}
          onUpdated={handleUpdated}
        />
      )}
      <div className="card">
        <table className="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Title</th>
              <th>Vendor</th>
              <th>Total</th>
              <th>Status</th>
              <th>Last update</th>
            </tr>
          </thead>
          <tbody>
            {requests.map((request) => {
              const latestEvent = request.status_history[request.status_history.length - 1];
              return (
                <tr
                  key={request.id}
                  className="table-row-clickable"
                  onClick={() => setSelectedRequest(request)}
                >
                  <td>{request.id}</td>
                  <td>{request.title}</td>
                  <td>{request.vendor_name}</td>
                  <td>{fmt(request.total_cost)}</td>
                  <td><span className={`status-badge status-${request.status}`}>{STATUS_LABEL[request.status]}</span></td>
                  <td>{latestEvent ? `${STATUS_LABEL[latestEvent.to_status] ?? latestEvent.to_status} at ${latestEvent.at}` : "-"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
