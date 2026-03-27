import { useMemo, useRef, useState } from "react";
import { createRequest, extract } from "../data/api";
import {
  classifyCommodityGroup,
  emptyForm,
  emptyLine,
  fmt,
  validate,
} from "../utils/procurementUtils";

export default function IntakeForm({ onSubmit, onNotice, onError }) {
  const [form, setForm] = useState(emptyForm());
  const [errors, setErrors] = useState({});
  const [extracting, setExtracting] = useState(false);
  const [extracted, setExtracted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [extractWarnings, setExtractWarnings] = useState([]);
  const inputRef = useRef(null);

  const lineTotal = useMemo(
    () =>
      form.order_lines.reduce(
        (sum, line) => sum + (parseFloat(line.total_price) || 0),
        0,
      ),
    [form.order_lines],
  );

  // Use the AI-extracted total_cost when available (includes VAT/shipping from the offer).
  // Fall back to summing line items when user fills the form manually.
  const total = form.total_cost > 0 ? form.total_cost : lineTotal;

  const commodity = useMemo(() => classifyCommodityGroup(form), [form]);

  const setField = (field, value) =>
    setForm((prev) => ({ ...prev, [field]: value }));

  const updateLine = (id, field, value) => {
    setForm((prev) => ({
      ...prev,
      total_cost: 0, // user is manually editing — fall back to line sum
      order_lines: prev.order_lines.map((line) => {
        if (line.id !== id) return line;
        const updated = { ...line, [field]: value };
        const unitPrice =
          parseFloat(field === "unit_price" ? value : updated.unit_price) || 0;
        const amount =
          parseFloat(field === "amount" ? value : updated.amount) || 0;
        const discount =
          parseFloat(field === "discount" ? value : updated.discount) || 0;
        updated.total_price = parseFloat(
          (unitPrice * amount * (1 - discount / 100)).toFixed(2),
        );
        return updated;
      }),
    }));
  };

  const removeLine = (id) => {
    setForm((prev) => ({
      ...prev,
      order_lines:
        prev.order_lines.length === 1
          ? prev.order_lines
          : prev.order_lines.filter((line) => line.id !== id),
    }));
  };

  const addLine = () => {
    setForm((prev) => ({
      ...prev,
      order_lines: [...prev.order_lines, emptyLine()],
    }));
  };

  const handleExtract = async (file) => {
    if (!file) return;
    setExtracting(true);
    try {
      const data = await extract(file);
      setForm((prev) => ({
        ...prev,
        vendor_name: data.vendor_name || prev.vendor_name,
        vat_id: data.vat_id || prev.vat_id,
        department: data.department || prev.department,
        commodity_group_id: data.commodity_group_id || prev.commodity_group_id,
        total_cost: data.total_cost || prev.total_cost,
        order_lines:
          data.order_lines?.map((line) => ({
            ...line,
            id: Date.now() + Math.random(),
          })) || prev.order_lines,
      }));
      if (data.warnings?.length) {
        setExtractWarnings(data.warnings);
      }
      onNotice("Vendor offer extracted. Review and submit.");
      setExtracted(true);
    } catch (err) {
      onError(err.message || "Extraction failed. Fill details manually.");
    } finally {
      setExtracting(false);
      // Reset file input so selecting the same file again triggers onChange
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const handleSubmit = async () => {
    const payload = {
      ...form,
      commodity_group_id: commodity.id,
      total_cost: total,
    };

    const validationErrors = validate(payload);
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    setErrors({});
    setSubmitting(true);
    try {
      const created = await createRequest(payload);
      setForm(emptyForm());
      onSubmit(`Request ${created.id} submitted successfully.`);
    } catch (err) {
      onError(err.message || "Failed to submit request. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="stack">
      {extractWarnings.length > 0 && (
        <div className="extraction-warning">
          <div className="extraction-warning-body">
            <strong>⚠ Extraction may be incomplete</strong>
            <ul>
              {extractWarnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
          <button
            className="extraction-warning-close"
            onClick={(e) => {
              e.stopPropagation();
              setExtractWarnings([]);
            }}
            aria-label="Dismiss warning"
          >
            ×
          </button>
        </div>
      )}
      <section className="card">
        <h2>Vendor Offer Upload</h2>
        <div className="upload-zone" onClick={() => inputRef.current?.click()}>
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,image/*"
            style={{ display: "none" }}
            onChange={(e) => handleExtract(e.target.files[0])}
          />
          <div className="upload-text">
            {extracting ? "Extracting..." : "Click to upload document"}
          </div>
          <div className="upload-sub">PDF</div>
        </div>
      </section>

      {extracted && (
        <section className="card">
          <h2>Request details</h2>

          <div className="form-grid">
            <div className="field">
              <label>Requestor name *</label>
              <input
                value={form.requestor_name}
                onChange={(e) => setField("requestor_name", e.target.value)}
                className={errors.requestor_name ? "error" : ""}
              />
              {errors.requestor_name && (
                <small className="error-text">{errors.requestor_name}</small>
              )}
            </div>

            <div className="field">
              <label>Department *</label>
              <input
                value={form.department}
                onChange={(e) => setField("department", e.target.value)}
                className={errors.department ? "error" : ""}
              />
              {errors.department && (
                <small className="error-text">{errors.department}</small>
              )}
            </div>

            <div className="field full">
              <label>Title / short description *</label>
              <input
                value={form.title}
                onChange={(e) => setField("title", e.target.value)}
                className={errors.title ? "error" : ""}
              />
              {errors.title && (
                <small className="error-text">{errors.title}</small>
              )}
            </div>

            <div className="field">
              <label>Vendor name *</label>
              <input
                value={form.vendor_name}
                onChange={(e) => setField("vendor_name", e.target.value)}
                className={errors.vendor_name ? "error" : ""}
              />
              {errors.vendor_name && (
                <small className="error-text">{errors.vendor_name}</small>
              )}
            </div>

            <div className="field">
              <label>VAT ID *</label>
              <input
                value={form.vat_id}
                onChange={(e) => setField("vat_id", e.target.value)}
                className={errors.vat_id ? "error" : ""}
              />
              {errors.vat_id && (
                <small className="error-text">{errors.vat_id}</small>
              )}
            </div>

            <div className="field full">
              <label>Commodity group</label>
              <input readOnly value={`${commodity.id} — ${commodity.label}`} />
            </div>
          </div>

          <div className="lines-block">
            <label>Order lines *</label>
            <div className="order-lines">
              <div className="line-header">
                <label>Description</label>
                <label>Unit price</label>
                <label>Qty</label>
                <label>Unit</label>
                <label>Discount %</label>
                <label>Total</label>
                <label></label>
              </div>

              {form.order_lines.map((line, index) => (
                <div className="order-line" key={line.id}>
                  <input
                    value={line.position_description}
                    onChange={(e) =>
                      updateLine(
                        line.id,
                        "position_description",
                        e.target.value,
                      )
                    }
                    className={errors[`line_${index}_desc`] ? "error" : ""}
                  />
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={line.unit_price}
                    onChange={(e) =>
                      updateLine(line.id, "unit_price", e.target.value)
                    }
                    className={errors[`line_${index}_price`] ? "error" : ""}
                  />
                  <input
                    type="number"
                    min="0"
                    value={line.amount}
                    onChange={(e) =>
                      updateLine(line.id, "amount", e.target.value)
                    }
                    className={errors[`line_${index}_amount`] ? "error" : ""}
                  />
                  <input
                    value={line.unit}
                    onChange={(e) =>
                      updateLine(line.id, "unit", e.target.value)
                    }
                  />
                  <input
                    type="number"
                    min="0"
                    max="100"
                    step="0.01"
                    value={line.discount ?? ""}
                    onChange={(e) =>
                      updateLine(line.id, "discount", e.target.value)
                    }
                  />
                  <input
                    readOnly
                    value={line.total_price ? fmt(line.total_price) : ""}
                  />
                  <button
                    className="remove-btn"
                    onClick={() => removeLine(line.id)}
                  >
                    ×
                  </button>
                </div>
              ))}

              <button className="add-line-btn" onClick={addLine}>
                + Add line
              </button>
            </div>
          </div>

          <div className="total-row">
            <span>Total cost</span>
            <strong>{fmt(total)}</strong>
          </div>

          <div className="actions">
            <button
              className="button secondary"
              onClick={() => setForm(emptyForm())}
            >
              Clear
            </button>
            <button
              className="button primary"
              onClick={handleSubmit}
              disabled={submitting}
            >
              {submitting ? "Submitting..." : "Submit request"}
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
