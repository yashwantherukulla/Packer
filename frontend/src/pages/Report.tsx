import { useParams } from "react-router-dom";
import { ReportView } from "@/components/ReportView";
import { useReport } from "@/hooks/useJob";

export function Report() {
  const { id = "" } = useParams();
  const report = useReport(id || null);
  if (!report.data) return <p>Loading report…</p>;
  return <ReportView report={report.data} />;
}
