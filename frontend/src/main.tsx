import { StrictMode, useEffect, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import "./styles.css";
import { AppProvider, useApp, type Role } from "./app";
import { DemoBar, Header, Toasts, Tour } from "./components/Shell";
import { Skeleton } from "./components/ui";
import Login, { Forgot, SetPassword } from "./pages/Login";
import Signup, { Verify, Welcome } from "./pages/Signup";
import { ComplaintDone, FileComplaint, MyComplaints, TrackComplaint } from "./pages/Complain";
import Today from "./pages/Today";
import Cases from "./pages/Cases";
import CaseDetail from "./pages/CaseDetail";
import Institutions, { Institution360 } from "./pages/Institutions";
import Overlaps, { OverlapDetail } from "./pages/Overlaps";
import Dashboard from "./pages/Dashboard";
import Reports from "./pages/Reports";
import Admin, { Emails, Audit, Inbox } from "./pages/Admin";
import { About, PublicCheck, Submit, Calendar } from "./pages/Public";

import { HOME } from "./home";

const STAFF: Role[] = ["desk_officer", "unit_head", "coordinator", "management", "admin"];

function Guard({ roles = STAFF, children }: { roles?: Role[]; children: ReactNode }) {
  const { me, loading } = useApp();
  if (loading) return <main><div className="wrap"><Skeleton /></div></main>;
  if (!me) return <Navigate to="/login" replace />;
  if (!roles.includes(me.role)) return <Navigate to={HOME[me.role]} replace />;
  return <>{children}</>;
}

function Home() {
  const { me, loading } = useApp();
  if (loading) return <main><div className="wrap"><Skeleton /></div></main>;
  return <Navigate to={me ? HOME[me.role] : "/login"} replace />;
}

const OFFICE: Role[] = ["desk_officer", "unit_head", "coordinator"];

function App() {
  const { t, lang } = useApp();
  useEffect(() => { document.title = t("SAMANVAY · Institution complaint coordination"); }, [t, lang]);
  return (
    <>
      <a className="skip" href="#main">{t("Skip to content")}</a>
      <DemoBar />
      <Header />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/set-password" element={<SetPassword />} />
        <Route path="/forgot" element={<Forgot />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/verify" element={<Verify />} />
        <Route path="/welcome" element={<Guard roles={["college"]}><Welcome /></Guard>} />
        <Route path="/file" element={<Guard roles={["college"]}><FileComplaint /></Guard>} />
        <Route path="/my" element={<Guard roles={["college"]}><MyComplaints /></Guard>} />
        <Route path="/my/:ref" element={<Guard roles={["college"]}><TrackComplaint /></Guard>} />
        <Route path="/my/:ref/done" element={<Guard roles={["college"]}><ComplaintDone /></Guard>} />
        <Route path="/about" element={<About />} />
        <Route path="/check" element={<PublicCheck />} />
        <Route path="/check/:ref" element={<PublicCheck />} />
        <Route path="/complain" element={<Submit />} />
        <Route path="/" element={<Home />} />
        <Route path="/today" element={<Guard roles={OFFICE}><Today /></Guard>} />
        <Route path="/cases" element={<Guard><Cases /></Guard>} />
        <Route path="/cases/:ref" element={<Guard><CaseDetail /></Guard>} />
        <Route path="/institutions" element={<Guard><Institutions /></Guard>} />
        <Route path="/institutions/:id" element={<Guard><Institution360 /></Guard>} />
        <Route path="/overlaps" element={<Guard><Overlaps /></Guard>} />
        <Route path="/overlaps/:id" element={<Guard><OverlapDetail /></Guard>} />
        <Route path="/dashboard" element={<Guard><Dashboard /></Guard>} />
        <Route path="/reports" element={<Guard><Reports /></Guard>} />
        <Route path="/calendar" element={<Guard><Calendar /></Guard>} />
        <Route path="/audit" element={<Guard><Audit /></Guard>} />
        <Route path="/emails" element={<Guard roles={["admin", "management", "coordinator"]}><Emails /></Guard>} />
        <Route path="/admin" element={<Guard roles={["admin"]}><Admin /></Guard>} />
        <Route path="/inbox" element={<Guard><Inbox /></Guard>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <Toasts />
      <Tour />
    </>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode><BrowserRouter><AppProvider><App /></AppProvider></BrowserRouter></StrictMode>,
);
