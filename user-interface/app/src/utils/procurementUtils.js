export const fmt = (value) =>
  new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(
    value,
  );

export const emptyLine = () => ({
  id: Date.now() + Math.random(),
  position_description: "",
  unit_price: "",
  amount: "",
  unit: "",
  discount: "",
  total_price: "",
});

export const emptyForm = () => ({
  requestor_name: "",
  title: "",
  vendor_name: "",
  vat_id: "",
  department: "",
  commodity_group_id: "",
  order_lines: [emptyLine()],
  total_cost: 0,
});

export const COMMODITY_GROUPS = {
  "001": "Accommodation Rentals",
  "002": "Membership Fees",
  "003": "Workplace Safety",
  "004": "Consulting",
  "005": "Financial Services",
  "006": "Fleet Management",
  "007": "Recruitment Services",
  "008": "Professional Development",
  "009": "Miscellaneous Services",
  "010": "Insurance",
  "011": "Electrical Engineering",
  "012": "Facility Management Services",
  "013": "Security",
  "014": "Renovations",
  "015": "Office Equipment",
  "016": "Energy Management",
  "017": "Maintenance",
  "018": "Cafeteria and Kitchenettes",
  "019": "Cleaning",
  "020": "Audio and Visual Production",
  "021": "Books/Videos/CDs",
  "022": "Printing Costs",
  "023": "Software Development for Publishing",
  "024": "Material Costs",
  "025": "Shipping for Production",
  "026": "Digital Product Development",
  "027": "Pre-production",
  "028": "Post-production Costs",
  "029": "Hardware",
  "030": "IT Services",
  "031": "Software",
  "032": "Courier, Express and Postal Services",
  "033": "Warehousing and Material Handling",
  "034": "Transportation Logistics",
  "035": "Delivery Services",
  "036": "Advertising",
  "037": "Outdoor Advertising",
  "038": "Marketing Agencies",
  "039": "Direct Mail",
  "040": "Customer Communication",
  "041": "Online Marketing",
  "042": "Events",
  "043": "Promotional Materials",
  "044": "Warehouse and Operational Equipment",
  "045": "Production Machinery",
  "046": "Spare Parts",
  "047": "Internal Transportation",
  "048": "Production Materials",
  "049": "Consumables",
  "050": "Maintenance and Repairs",
};

export function classifyCommodityGroup(form) {
  // Use backend-provided ID if valid, else default to '009'
  if (form.commodity_group_id && COMMODITY_GROUPS[form.commodity_group_id]) {
    return {
      id: form.commodity_group_id,
      label: COMMODITY_GROUPS[form.commodity_group_id],
    };
  }
  return { id: "009", label: COMMODITY_GROUPS["009"] };
}

export function validate(form) {
  const errors = {};

  if (!form.requestor_name.trim()) errors.requestor_name = "Required";
  if (!form.title.trim()) errors.title = "Required";
  if (!form.vendor_name.trim()) errors.vendor_name = "Required";

  if (!form.vat_id.trim()) {
    errors.vat_id = "Required";
  } else if (!/^[A-Z]{2}\d{7,12}$/.test(form.vat_id.trim())) {
    errors.vat_id = "Invalid VAT ID (e.g. DE123456789)";
  }

  if (!form.department.trim()) errors.department = "Required";
  if (!form.commodity_group_id) errors.commodity_group_id = "Required";

  form.order_lines.forEach((line, index) => {
    if (!line.position_description) errors[`line_${index}_desc`] = "Required";
    if (!line.unit_price || line.unit_price <= 0)
      errors[`line_${index}_price`] = "Invalid";
    if (!line.amount || line.amount <= 0)
      errors[`line_${index}_amount`] = "Invalid";
  });

  return errors;
}
