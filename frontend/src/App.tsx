import { useState, useEffect, useRef } from 'react';
import { 
  CheckCircle, RefreshCw, GitCommit, FileText, 
  Terminal, ShieldAlert, X, Shield, Cpu, Activity, Database, FolderGit2
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell } from 'recharts';
import WorkspacePanel from './WorkspacePanel';

interface TimelineEvent {
  timestamp: string;
  event_type: string;
  description: string;
  metadata: any;
}

interface Evidence {
  id: string;
  source: string;
  timestamp: string;
  evidence_type: string;
  content: any;
  relevance: string;
  reliability: number;
}

interface Hypothesis {
  id: string;
  description: string;
  supporting_evidence: string[];
  contradicting_evidence: string[];
  probability: number;
  status: string;
}

interface Experiment {
  id: string;
  hypothesis_id: string;
  name: string;
  description: string;
  script: string;
  status: string;
  result: any;
}

interface IncidentState {
  incident_id: string;
  incident_type: string;
  severity: string;
  symptoms: any;
  timeline: TimelineEvent[];
  evidence: Evidence[];
  hypotheses: Hypothesis[];
  experiments: Experiment[];
  belief_scores: { [key: string]: number };
  confirmed_root_cause: string | null;
  confidence: number;
  human_approval_required: boolean;
  investigation_status: string;
  logs: string[];
  next_action: string | null;
  causal_graph?: {
    nodes: any[];
    edges: any[];
  };
  counterfactual_verification?: {
    status: string;
    variable_tested: string;
    real_world_value: string;
    real_world_metric: string;
    counterfactual_value: string;
    counterfactual_metric: string;
    proof: string;
  };
}

const documentsData = {
  tech_report: {
    title: "NeoGuard Technical & Business Report",
    subtitle: "Companion technical and business assessment for the newborn screening system.",
    author: "Pravin",
    date: "August 22, 2026",
    status: "Engineering Prototype Deliverable",
    downloadUrl: "/api/documents/NeoGuard_Technical_Business_Report.docx",
    summary: [
      "NeoGuard turns an ordinary smartphone, plus a low-cost attachment, into a standardized screening tool for neonatal jaundice.",
      "Sclera (white of the eye) is the preferred imaging site to avoid the melanin skin-tone confound found in skin-only jaundice apps.",
      "Internal validation on 1,200 synthetic captures shows MAE of 1.6 mg/dL, high-risk screening sensitivity of 80%, and specificity of 95.9%.",
      "Cross-check on 760 real photos (Kaggle/NJN) achieves 74.7% accuracy (5-fold CV mean accuracy 73.5%) and 50% sensitivity without a calibration target."
    ],
    details: "Moving from the initial pitch deck to a working foundation, this report details competitive positioning (e.g., comparing against BiliCam, transcutaneous bilirubinometers, and gold standard serum tests), clinical justifications, and a phased go-to-market plan targeting clinics and public health NGOs."
  },
  study_protocol: {
    title: "NeoGuard Clinical Study Protocol",
    subtitle: "Diagnostic-accuracy validation protocol for CDSCO IRB submission.",
    author: "Pravin",
    date: "August 22, 2026",
    status: "IRB Pre-submission Planning Draft",
    downloadUrl: "/api/documents/NeoGuard_Clinical_Study_Protocol.docx",
    summary: [
      "Estimates diagnostic accuracy (Sensitivity and Specificity) of NeoGuard's HIGH-risk category against reference Total Serum Bilirubin (TSB).",
      "Target population: Term/near-term newborns (gestational age >=35 weeks, postnatal age 24-168 hours) undergoing clinically indicated TSB draws.",
      "Double-blind design: NeoGuard operators and laboratory personnel are blinded to each other's results.",
      "Target sample size: ~900-1,200 newborns to obtain 50-60 true positive cases based on 8-10% local prevalence assumptions."
    ],
    details: "The protocol details inclusion/exclusion criteria, capture-to-draw time window (<=60 mins), standardized data-collection SOP (Appendix B) to eliminate lighting/operator confounds, and template outreach letters to partner hospitals (Appendix C)."
  },
  hardware_spec: {
    title: "NeoGuard Hardware Specification & BOM",
    subtitle: "Optical design, light diffusion, and prototyping bill of materials.",
    author: "Pravin",
    date: "August 22, 2026",
    status: "DRAFT Engineering Reference",
    downloadUrl: "/api/documents/NeoGuard_Hardware_Specification_BOM.docx",
    summary: [
      "Enclosure: Parametric clip-on housing (68 x 42 x 26 mm) with a 40mm fixed standoff to ensure a standardized capture scale.",
      "Illumination: White SMD LED ring light (~5600K daylight-balanced, CRI>=90) to avoid color distortion.",
      "Glare Prevention: Translucent PMMA diffuser plate over the LEDs prevents hard specular reflections on the baby's eye.",
      "Color Calibration: Matte target sticker containing white, gray, and black reference patches (sRGB 255/128/30) in every frame."
    ],
    details: "Includes a detailed Bill of Materials (BOM) for prototype batches estimating the cost per unit at ₹610 (~$7.50 USD), and outlines a v2 narrow-band 460nm LED dual-wavelength upgrade option."
  },
  regulatory_qms: {
    title: "NeoGuard Regulatory Strategy & QMS",
    subtitle: "SaMD classification pathways and data protection framework.",
    author: "Pravin",
    date: "August 22, 2026",
    status: "Planning Strategy Document",
    downloadUrl: "/api/documents/NeoGuard_Regulatory_Strategy_QMS.docx",
    summary: [
      "Classification: Software as a Medical Device (SaMD) + Passive Optical Accessory.",
      "CDSCO Pathway: Class B (low-moderate risk) manufacturing/import licensing via the SUGAM portal.",
      "International Markets: US FDA Class II (likely 510(k) or De Novo) and EU MDR Class IIa (Rule 11).",
      "Privacy Safeguards: Strict alignment with India's Digital Personal Data Protection (DPDP) Act 2023 (parental consent, purpose limitation, data erasure)."
    ],
    details: "Outlines a Quality Management System skeleton aligned to IEC 62304 Safety Class B for software development lifecycle processes and details a clinical-worker competency training curriculum."
  },
  risk_file: {
    title: "NeoGuard Risk Management File",
    subtitle: "ISO 14971:2019-aligned risk analysis and mitigations.",
    author: "Pravin",
    date: "August 22, 2026",
    status: "DRAFT Prototype Hazard Triage",
    downloadUrl: "/api/documents/NeoGuard_Risk_Management_File.docx",
    summary: [
      "Scope: Applies ISO 14971 process to identify hazards across the hardware attachment, software pipeline, and data handling.",
      "ALARP Hazards: 4 hazards controlled in code (H-2 AI false-neg, H-3 Quality gate, H-4 Calibration, H-5 Sclera ROI misdetection).",
      "Unacceptable Hazards: 8 hazards scored unacceptable pre-production due to lack of real clinical data and physical hardware testing.",
      "Risk-Benefit Conclusion: Acceptable for internal development, partner discussions, and IRB prep; NOT acceptable for clinical use."
    ],
    details: "Triage matrix maps out 12 distinct safety hazards. Mitigations implemented in code are verified, while operational and physical controls (hygiene SOPs, hardware drift checks) are logged as pending items."
  },
  research_paper: {
    title: "AI-Powered Jaundice Screening Paper",
    subtitle: "Academic PDF detailing the screening model and computer vision pipeline.",
    author: "NeoGuard Team",
    date: "August 22, 2026",
    status: "Research Paper (PDF)",
    downloadUrl: "/api/documents/AI-Powered-Non-Invasive-Neonatal-Jaundice-Screening.pdf",
    summary: [
      "Deep technical review of the skin and sclera color feature extraction algorithm.",
      "Detailed comparison of HSV vs CIE Lab color channels in quantifying bilirubin jaundice indices.",
      "Description of the gray-world and affine color-mapping math used for lighting normalization.",
      "Validation logs showing high model robustness against simulated ambient shadows and chromatic shifts."
    ],
    details: "This is the primary scientific publication backing the project. It describes the mathematical formulations behind the color calibration matrices and the region of interest segmenter."
  }
};

export default function App() {
  const [activeIncidentId, setActiveIncidentId] = useState<string>("104");
  const [incidentState, setIncidentState] = useState<IncidentState | null>(null);
  const [activeTab, setActiveTab] = useState<'timeline' | 'causal' | 'evidence' | 'sandbox' | 'findings'>('timeline');
  const [selectedDoc, setSelectedDoc] = useState<string>("tech_report");
  const [selectedEvidence, setSelectedEvidence] = useState<Evidence | null>(null);
  const [loading, setLoading] = useState(false);
  const [historyList, setHistoryList] = useState<any[]>([]);
  const [showWorkspace, setShowWorkspace] = useState(false);

  
  const wsRef = useRef<WebSocket | null>(null);
  const terminalEndRef = useRef<HTMLDivElement | null>(null);

  // Fetch past incidents list on load
  const fetchIncidentsList = async () => {
    try {
      const res = await fetch('/api/incidents');
      const data = await res.json();
      setHistoryList(data);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchIncidentsList();
  }, []);

  // Set up WebSocket connection for active incident
  useEffect(() => {
    if (!activeIncidentId) return;

    if (wsRef.current) {
      wsRef.current.close();
    }

    const wsUrl = `ws://${window.location.host}/ws/incidents/${activeIncidentId}`;
    console.log("Connecting to WebSocket:", wsUrl);
    
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const state = JSON.parse(event.data);
      setIncidentState(state);
    };

    ws.onclose = () => {
      console.log("WebSocket disconnected");
    };

    return () => {
      ws.close();
    };
  }, [activeIncidentId]);

  // Scroll terminal logs to bottom
  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [incidentState?.logs]);

  // Ingest/Trigger simulated incident scenario
  const handleTriggerIncident = async (scenarioId: string, _title: string, type: string) => {
    setLoading(true);
    try {
      // 1. Reset Simulator
      await fetch('/simulator/reset', { method: 'POST' });
      
      // 2. Inject Fault in Simulator
      let faultType = "";
      if (scenarioId === "104") faultType = "preprocessing_mismatch";
      if (scenarioId === "105") faultType = "wrong_model";
      if (scenarioId === "106") faultType = "data_drift";
      if (scenarioId === "107") faultType = "dependency_regression";
      if (scenarioId === "108") faultType = "resource_limit";

      await fetch(`/simulator/inject?fault_type=${faultType}`, { method: 'POST' });
      
      // 3. Trigger Autonomous Investigation API
      const symptoms = scenarioId === "108" 
        ? { accuracy: 0.942, latency: 2.41, error_rate: 0.12 }
        : { accuracy: 0.713, latency: 0.18, error_rate: 0.178 };

      await fetch('/api/investigate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          incident_id: scenarioId,
          incident_type: type,
          severity: "HIGH",
          symptoms: symptoms
        })
      });

      setActiveIncidentId(scenarioId);
      await fetchIncidentsList();
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  // Approve pending fix diff
  const handleApprovePatch = async () => {
    if (!activeIncidentId) return;
    try {
      await fetch(`/api/incidents/${activeIncidentId}/approve`, { method: 'POST' });
    } catch (e) {
      console.error(e);
    }
  };

  // Reset demo states
  const handleResetSimulator = async () => {
    try {
      await fetch('/simulator/reset', { method: 'POST' });
      alert("Simulator successfully restored to healthy parameters.");
    } catch (e) {
      console.error(e);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'RESOLVED':
        return <span className="px-3 py-1 text-xs rounded-full bg-emerald-500/15 border border-emerald-500/40 text-emerald-400 font-semibold uppercase tracking-wider flex items-center gap-1.5"><CheckCircle size={12} /> Resolved</span>;
      case 'AWAITING_APPROVAL':
        return <span className="px-3 py-1 text-xs rounded-full bg-amber-500/15 border border-amber-500/40 text-amber-400 font-semibold uppercase tracking-wider flex items-center gap-1.5 animate-pulse-soft"><ShieldAlert size={12} /> Patch Awaiting Approval</span>;
      case 'FAILED':
        return <span className="px-3 py-1 text-xs rounded-full bg-red-500/15 border border-red-500/40 text-red-400 font-semibold uppercase tracking-wider flex items-center gap-1.5"><X size={12} /> Investigation Failed</span>;
      case 'TRIAGING':
      case 'PLANNING':
      case 'EXPERIMENTING':
      case 'VERIFYING':
      case 'REPRODUCING':
        return <span className="px-3 py-1 text-xs rounded-full bg-blue-500/15 border border-blue-500/40 text-blue-400 font-semibold uppercase tracking-wider flex items-center gap-1.5 animate-pulse-soft"><RefreshCw size={12} className="animate-spin" /> {status}</span>;
      default:
        return <span className="px-3 py-1 text-xs rounded-full bg-gray-500/15 border border-gray-500/40 text-gray-400 font-semibold uppercase tracking-wider">{status}</span>;
    }
  };

  const getIncidentName = (id: string) => {
    if (id === "104") return "Mammography Classifier Accuracy Degradation";
    if (id === "105") return "Uncalibrated Version Deployment Skew";
    if (id === "106") return "Production Clinical Dataset Data Drift";
    if (id === "107") return "NumPy 2.0 Dependency Upgrade Regression";
    if (id === "108") return "max_workers Serial Thread Lock Latency Spike";
    return `Incident #${id}`;
  };

  // Format Recharts data
  const chartData = incidentState?.hypotheses?.map(h => ({
    name: h.id,
    probability: Math.round(h.probability * 100),
    description: h.description,
    status: h.status
  })) || [];

  return (
    <div className="min-h-screen bg-[#06090f] text-gray-200 flex flex-col antialiased selection:bg-blue-500/30">
      {/* HEADER */}
      <header className="border-b border-gray-800/80 bg-[#090d16] px-6 py-4 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="bg-gradient-to-tr from-blue-600 to-indigo-600 p-2 rounded-lg text-white shadow-lg shadow-blue-500/10">
            <Activity size={22} className="animate-pulse" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight bg-gradient-to-r from-white via-gray-100 to-gray-400 bg-clip-text text-transparent">
              RootCause AI
            </h1>
            <p className="text-xs text-blue-400/80 font-medium">Autonomous System Failure Investigation Agent</p>
          </div>
        </div>

        {/* DEMO CONTROLS */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400 font-semibold mr-1">Inject Fault Scenario:</span>
          <button 
            disabled={loading}
            onClick={() => handleTriggerIncident("104", "Mammography Accuracy Drop", "ML Performance Degradation")}
            className={`px-3 py-1.5 text-xs font-semibold rounded border transition ${activeIncidentId === "104" ? 'bg-blue-600 border-blue-500 text-white shadow-lg shadow-blue-500/20' : 'bg-gray-800/60 border-gray-700/80 hover:bg-gray-800 hover:border-gray-600'}`}
          >
            #104 Preprocessing
          </button>
          <button 
            disabled={loading}
            onClick={() => handleTriggerIncident("105", "Model Version Mismatch", "Deployment Version Skew")}
            className={`px-3 py-1.5 text-xs font-semibold rounded border transition ${activeIncidentId === "105" ? 'bg-blue-600 border-blue-500 text-white shadow-lg shadow-blue-500/20' : 'bg-gray-800/60 border-gray-700/80 hover:bg-gray-800 hover:border-gray-600'}`}
          >
            #105 Version Mismatch
          </button>
          <button 
            disabled={loading}
            onClick={() => handleTriggerIncident("106", "Data Drift", "Data Distribution Drift")}
            className={`px-3 py-1.5 text-xs font-semibold rounded border transition ${activeIncidentId === "106" ? 'bg-blue-600 border-blue-500 text-white shadow-lg shadow-blue-500/20' : 'bg-gray-800/60 border-gray-700/80 hover:bg-gray-800 hover:border-gray-600'}`}
          >
            #106 Data Drift
          </button>
          <button 
            disabled={loading}
            onClick={() => handleTriggerIncident("107", "Dependency Bug", "Dependency Regression")}
            className={`px-3 py-1.5 text-xs font-semibold rounded border transition ${activeIncidentId === "107" ? 'bg-blue-600 border-blue-500 text-white shadow-lg shadow-blue-500/20' : 'bg-gray-800/60 border-gray-700/80 hover:bg-gray-800 hover:border-gray-600'}`}
          >
            #107 Dependency
          </button>
          <button 
            disabled={loading}
            onClick={() => handleTriggerIncident("108", "Concurrency Latency", "Resource Limit Delay")}
            className={`px-3 py-1.5 text-xs font-semibold rounded border transition ${activeIncidentId === "108" ? 'bg-blue-600 border-blue-500 text-white shadow-lg shadow-blue-500/20' : 'bg-gray-800/60 border-gray-700/80 hover:bg-gray-800 hover:border-gray-600'}`}
          >
            #108 Latency Lock
          </button>
          <div className="h-6 w-[1px] bg-gray-800 mx-2"></div>
          <button 
            onClick={() => setShowWorkspace(true)}
            className="px-2.5 py-1.5 text-xs font-semibold rounded bg-emerald-600/80 hover:bg-emerald-600 text-white transition flex items-center gap-1.5"
            title="Connect a real repository for live codebase investigation"
          >
            <FolderGit2 size={12} /> Connect Workspace
          </button>
          <button 
            onClick={handleResetSimulator}
            className="px-2.5 py-1.5 text-xs font-semibold rounded bg-gray-900 border border-gray-800 hover:bg-gray-800/80 text-gray-300 transition"
            title="Reset Simulator to Healthy State"
          >
            Reset Env
          </button>
        </div>
      </header>

      {/* DASHBOARD CONTENT */}
      <main className="flex-1 flex overflow-hidden min-h-0">
        
        {/* LEFT COLUMN: Incident Information */}
        <section className="w-80 border-r border-gray-800/80 bg-[#070b13]/40 p-5 flex flex-col shrink-0 overflow-y-auto">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xs font-bold uppercase tracking-wider text-gray-400">Incident Registry</h2>
            <button onClick={fetchIncidentsList} className="text-gray-500 hover:text-gray-300">
              <RefreshCw size={12} />
            </button>
          </div>

          <div className="space-y-2 mb-6">
            {historyList.map(h => (
              <button 
                key={h.incident_id}
                onClick={() => setActiveIncidentId(h.incident_id)}
                className={`w-full text-left p-3 rounded-lg border transition text-xs flex flex-col gap-1.5 ${activeIncidentId === h.incident_id ? 'bg-[#0f172a] border-blue-500/50 text-white' : 'bg-gray-950/30 border-gray-800 hover:border-gray-700 text-gray-400'}`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold text-gray-200">Incident #{h.incident_id}</span>
                  <span className="text-[10px] text-gray-500">{new Date(h.created_at).toLocaleTimeString()}</span>
                </div>
                <span className="truncate font-semibold text-gray-300">{getIncidentName(h.incident_id)}</span>
                <div className="flex items-center gap-1.5 mt-1">
                  <span className={`w-1.5 h-1.5 rounded-full ${h.status === 'RESOLVED' ? 'bg-emerald-500' : h.status === 'AWAITING_APPROVAL' ? 'bg-amber-500' : 'bg-blue-500'}`}></span>
                  <span className="text-[10px] font-bold uppercase text-gray-500">{h.status}</span>
                </div>
              </button>
            ))}
          </div>

          {incidentState ? (
            <div className="flex-1 flex flex-col gap-4">
              <div className="border-t border-gray-800/80 pt-4">
                <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400 mb-3">Triaged Symptoms</h3>
                
                <div className="glass-panel rounded-xl p-4 space-y-3">
                  <div>
                    <div className="text-[10px] font-bold uppercase text-gray-400">Target Service</div>
                    <div className="text-xs font-semibold text-gray-200 mt-0.5">mammography-classifier-api</div>
                  </div>
                  <div>
                    <div className="text-[10px] font-bold uppercase text-gray-400">Incident Type</div>
                    <div className="text-xs font-semibold text-blue-400 mt-0.5">{incidentState.incident_type}</div>
                  </div>
                  <div className="grid grid-cols-2 gap-2 pt-2 border-t border-gray-800/40">
                    <div>
                      <div className="text-[10px] font-bold uppercase text-gray-500">Accuracy</div>
                      <div className={`text-base font-bold mt-0.5 ${incidentState.symptoms.accuracy < 0.8 ? 'text-red-400' : 'text-emerald-400'}`}>
                        {Math.round(incidentState.symptoms.accuracy * 1000) / 10}%
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] font-bold uppercase text-gray-500">Avg Latency</div>
                      <div className={`text-base font-bold mt-0.5 ${incidentState.symptoms.latency > 1.0 ? 'text-red-400' : 'text-gray-300'}`}>
                        {incidentState.symptoms.latency}s
                      </div>
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] font-bold uppercase text-gray-500">Error Rate</div>
                    <div className={`text-xs font-semibold mt-0.5 ${incidentState.symptoms.error_rate > 0.05 ? 'text-red-400' : 'text-gray-400'}`}>
                      {Math.round(incidentState.symptoms.error_rate * 1000) / 10}%
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex-grow flex items-center justify-center text-center text-xs text-gray-500">
              Select an incident to view diagnostics state.
            </div>
          )}
        </section>

        {/* CENTER COLUMN: Timeline and Workspace */}
        <section className="flex-1 border-r border-gray-800/80 flex flex-col min-w-0 bg-[#080d16]/20">
          
          {/* TABS */}
          <div className="flex border-b border-gray-800/80 bg-[#080c14] px-6 shrink-0 justify-between items-center">
            <div className="flex gap-4">
              <button 
                onClick={() => setActiveTab('timeline')}
                className={`py-3.5 text-xs font-bold uppercase tracking-wider border-b-2 transition ${activeTab === 'timeline' ? 'border-blue-500 text-blue-400' : 'border-transparent text-gray-400 hover:text-gray-200'}`}
              >
                Timeline
              </button>
              <button 
                onClick={() => setActiveTab('causal')}
                className={`py-3.5 text-xs font-bold uppercase tracking-wider border-b-2 transition ${activeTab === 'causal' ? 'border-blue-500 text-blue-400' : 'border-transparent text-gray-400 hover:text-gray-200'}`}
              >
                Causal Graph
              </button>
              <button 
                onClick={() => setActiveTab('evidence')}
                className={`py-3.5 text-xs font-bold uppercase tracking-wider border-b-2 transition ${activeTab === 'evidence' ? 'border-blue-500 text-blue-400' : 'border-transparent text-gray-400 hover:text-gray-200'}`}
              >
                Evidence Board
              </button>
              <button 
                onClick={() => setActiveTab('sandbox')}
                className={`py-3.5 text-xs font-bold uppercase tracking-wider border-b-2 transition ${activeTab === 'sandbox' ? 'border-blue-500 text-blue-400' : 'border-transparent text-gray-400 hover:text-gray-200'}`}
              >
                Sandbox Logs
              </button>
              <button 
                onClick={() => setActiveTab('findings')}
                className={`py-3.5 text-xs font-bold uppercase tracking-wider border-b-2 transition ${activeTab === 'findings' ? 'border-blue-500 text-blue-400' : 'border-transparent text-gray-400 hover:text-gray-200'}`}
              >
                WE WILL WIN Findings
              </button>
            </div>
            
            {incidentState && (
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-gray-400 font-semibold uppercase">Loop Status:</span>
                {getStatusBadge(incidentState.investigation_status)}
              </div>
            )}
          </div>

          {/* TAB BODY */}
          <div className="flex-1 overflow-y-auto p-6">
                       {/* TIMELINE TAB */}
            {activeTab === 'timeline' && incidentState && (
              <div className="max-w-2xl mx-auto py-4">
                <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400 mb-6">Investigation Timeline</h3>
                
                <div className="relative border-l border-gray-800 ml-4 space-y-6">
                  {incidentState.timeline.map((evt, idx) => (
                    <div key={idx} className="relative pl-8">
                      {/* Event Dot */}
                      <span className={`absolute -left-[9px] top-1 w-4 h-4 rounded-full border-4 border-[#06090f] flex items-center justify-center ${evt.event_type === 'DEPLOYMENT' ? 'bg-amber-500' : evt.event_type === 'ALERT' ? 'bg-red-500' : 'bg-blue-500'}`}></span>
                      
                       <div className="text-[10px] text-gray-500 font-bold uppercase">{new Date(evt.timestamp).toLocaleTimeString()} • {evt.event_type}</div>
                      <div className="text-sm font-semibold text-gray-200 mt-1">{evt.description}</div>
                      
                      {evt.metadata && Object.keys(evt.metadata).length > 0 && (
                        <div className="mt-2 text-xs bg-gray-950/40 border border-gray-850 p-2.5 rounded-lg text-gray-400 max-h-20 overflow-y-auto font-mono">
                          {JSON.stringify(evt.metadata, null, 2)}
                        </div>
                      )}
                    </div>
                  ))}
 
                  {/* Dynamic Loop Tasks */}
                  {incidentState.experiments.map((exp, idx) => (
                    <div key={idx} className="relative pl-8">
                      <span className={`absolute -left-[9px] top-1 w-4 h-4 rounded-full border-4 border-[#06090f] flex items-center justify-center ${exp.status === 'COMPLETED' ? 'bg-emerald-500' : exp.status === 'FAILED' ? 'bg-red-500' : 'bg-blue-500 animate-pulse-soft'}`}></span>
                      
                      <div className="text-[10px] text-gray-500 font-bold uppercase">EXPERIMENT RUN • {exp.id}</div>
                      <div className="text-sm font-semibold text-gray-200 mt-1">{exp.name}</div>
                      <div className="text-xs text-gray-400 mt-0.5">{exp.description}</div>
                      
                      {exp.result && exp.result.stdout && (
                        <div className="mt-2 text-xs bg-black/30 border border-gray-800/50 p-3 rounded-lg text-emerald-400 font-mono max-h-32 overflow-y-auto whitespace-pre-wrap">
                          {exp.result.stdout}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* CAUSAL GRAPH TAB */}
            {activeTab === 'causal' && incidentState && (() => {
              const graph = incidentState.causal_graph || {
                nodes: [
                  { id: "git_commit", label: "Git Deployment Change", type: "change", status: "active" },
                  { id: "H1", label: "H1: Data Drift", type: "variable", probability: incidentState.belief_scores?.H1 || 0.20, status: incidentState.hypotheses?.find(h => h.id === 'H1')?.status || 'ACTIVE' },
                  { id: "H2", label: "H2: Model Mismatch", type: "variable", probability: incidentState.belief_scores?.H2 || 0.20, status: incidentState.hypotheses?.find(h => h.id === 'H2')?.status || 'ACTIVE' },
                  { id: "H3", label: "H3: Preprocessing Mismatch", type: "variable", probability: incidentState.belief_scores?.H3 || 0.40, status: incidentState.hypotheses?.find(h => h.id === 'H3')?.status || 'ACTIVE' },
                  { id: "H4", label: "H4: Dependency Upgrade", type: "variable", probability: incidentState.belief_scores?.H4 || 0.10, status: incidentState.hypotheses?.find(h => h.id === 'H4')?.status || 'ACTIVE' },
                  { id: "H5", label: "H5: Resource Concurrency", type: "variable", probability: incidentState.belief_scores?.H5 || 0.10, status: incidentState.hypotheses?.find(h => h.id === 'H5')?.status || 'ACTIVE' },
                  { id: "accuracy", label: "Accuracy Drop", type: "symptom", status: (incidentState.symptoms.accuracy < 0.85) ? "failing" : "nominal" },
                  { id: "latency", label: "Latency Spike", type: "symptom", status: (incidentState.symptoms.latency > 1.0) ? "failing" : "nominal" }
                ],
                edges: [
                  { from: "git_commit", to: "H1", label: "Commit check", status: "possible" },
                  { from: "git_commit", to: "H2", label: "Commit check", status: "possible" },
                  { from: "git_commit", to: "H3", label: "Commit check", status: "possible" },
                  { from: "git_commit", to: "H4", label: "Commit check", status: "possible" },
                  { from: "git_commit", to: "H5", label: "Commit check", status: "possible" },
                  { from: "H1", to: "accuracy", label: "causes drop", status: "possible" },
                  { from: "H2", to: "accuracy", label: "causes drop", status: "possible" },
                  { from: "H3", to: "accuracy", label: "causes drop", status: "possible" },
                  { from: "H4", to: "accuracy", label: "causes drop", status: "possible" },
                  { from: "H5", to: "latency", label: "causes spike", status: "possible" }
                ]
              };

              const positions: Record<string, { x: number, y: number }> = {
                git_commit: { x: 300, y: 50 },
                H1: { x: 75, y: 170 },
                H2: { x: 185, y: 170 },
                H3: { x: 300, y: 170 },
                H4: { x: 415, y: 170 },
                H5: { x: 525, y: 170 },
                accuracy: { x: 185, y: 290 },
                latency: { x: 415, y: 290 }
              };

              return (
                <div className="max-w-4xl mx-auto py-2 flex flex-col gap-6">
                  <div className="flex justify-between items-start">
                    <div>
                      <h3 className="text-sm font-bold text-white uppercase tracking-wider">Autonomous Causal Failure Graph</h3>
                      <p className="text-xs text-gray-400 mt-1">
                        Active causal mapping: paths and nodes are probed dynamically. Reverting the verified cause proves causality.
                      </p>
                    </div>
                    {incidentState.counterfactual_verification && (
                      <span className="px-2.5 py-1 text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/25 rounded font-bold uppercase tracking-wider animate-pulse-soft">Causality Formally Proven</span>
                    )}
                  </div>
                  
                  <div className="glass-panel p-6 rounded-2xl flex items-center justify-center bg-gray-950/40 border border-gray-800/80">
                    <svg viewBox="0 0 600 350" className="w-full max-w-2xl h-auto">
                      <defs>
                        <marker id="arrow-confirmed" viewBox="0 0 10 10" refX="28" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                          <path d="M 0 0 L 10 5 L 0 10 z" fill="#10b981" />
                        </marker>
                        <marker id="arrow-possible" viewBox="0 0 10 10" refX="28" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                          <path d="M 0 0 L 10 5 L 0 10 z" fill="#4b5563" />
                        </marker>
                        <marker id="arrow-refuted" viewBox="0 0 10 10" refX="28" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                          <path d="M 0 0 L 10 5 L 0 10 z" fill="#ef4444" opacity="0.3" />
                        </marker>
                        <marker id="arrow-correlated" viewBox="0 0 10 10" refX="28" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                          <path d="M 0 0 L 10 5 L 0 10 z" fill="#3b82f6" />
                        </marker>
                      </defs>

                      {/* Render Edges */}
                      {graph.edges.map((edge, idx) => {
                        const fromPos = positions[edge.from];
                        const toPos = positions[edge.to];
                        if (!fromPos || !toPos) return null;
                        
                        let strokeColor = '#374151';
                        let strokeWidth = 1.5;
                        let strokeDasharray = undefined;
                        let opacity = 1.0;
                        
                        if (edge.status === 'confirmed') {
                          strokeColor = '#10b981';
                          strokeWidth = 3;
                        } else if (edge.status === 'refuted') {
                          strokeColor = '#ef4444';
                          strokeWidth = 1;
                          strokeDasharray = '3,3';
                          opacity = 0.3;
                        } else if (edge.status === 'correlated') {
                          strokeColor = '#3b82f6';
                          strokeWidth = 2;
                        } else if (edge.status === 'possible') {
                          strokeColor = '#4b5563';
                          strokeDasharray = '5,5';
                        }
                        
                        return (
                          <g key={idx} opacity={opacity}>
                            <line
                              x1={fromPos.x}
                              y1={fromPos.y}
                              x2={toPos.x}
                              y2={toPos.y}
                              stroke={strokeColor}
                              strokeWidth={strokeWidth}
                              strokeDasharray={strokeDasharray}
                              markerEnd={`url(#arrow-${edge.status})`}
                            />
                            {edge.status === 'confirmed' && (
                              <circle r="4" fill="#10b981">
                                <animateMotion
                                  dur="2.5s"
                                  repeatCount="indefinite"
                                  path={`M ${fromPos.x} ${fromPos.y} L ${toPos.x} ${toPos.y}`}
                                />
                              </circle>
                            )}
                          </g>
                        );
                      })}

                      {/* Render Nodes */}
                      {graph.nodes.map((node) => {
                        const pos = positions[node.id];
                        if (!pos) return null;
                        
                        let baseColor = 'bg-gray-900/60 border-gray-800 text-gray-400';
                        let ringColor = 'ring-gray-900/20';
                        let glowClass = '';
                        
                        if (node.status === 'VERIFIED' || node.status === 'resolved') {
                          baseColor = 'bg-emerald-950/40 border-emerald-500/80 text-emerald-300';
                          ringColor = 'ring-emerald-500/20';
                          glowClass = 'stroke-emerald-500/30 animate-pulse';
                        } else if (node.status === 'FALSIFIED' || node.status === 'falsified') {
                          baseColor = 'bg-red-950/10 border-red-950 text-gray-600';
                          ringColor = 'ring-red-950/10';
                        } else if (node.id === 'git_commit') {
                          baseColor = 'bg-amber-950/20 border-amber-500/60 text-amber-300';
                          ringColor = 'ring-amber-500/10';
                        } else if (node.id === 'accuracy' || node.id === 'latency') {
                          const active = node.status === 'failing';
                          baseColor = active ? 'bg-red-950/40 border-red-500/80 text-red-300' : 'bg-gray-900 border-gray-800 text-gray-500';
                          ringColor = active ? 'ring-red-500/20' : 'ring-gray-900/10';
                        } else if (node.status === 'ACTIVE' || node.status === 'candidate') {
                          baseColor = 'bg-blue-950/20 border-blue-500/60 text-blue-300';
                          ringColor = 'ring-blue-500/10';
                        }
                        
                        return (
                          <g key={node.id} transform={`translate(${pos.x}, ${pos.y})`}>
                            {glowClass && <circle r="25" fill="none" className={glowClass} strokeWidth="2" />}
                            <circle r="22" fill="none" className="stroke-gray-800/40" strokeWidth="1" />
                            
                            <foreignObject x="-30" y="-30" width="60" height="60">
                              <div className="w-full h-full flex items-center justify-center">
                                <div className={`w-10 h-10 rounded-full border flex items-center justify-center font-bold text-xs select-none shadow-lg transition-transform hover:scale-110 ${baseColor} ${ringColor}`}>
                                  {node.id === 'git_commit' ? 'Git' : node.id === 'accuracy' ? 'Acc' : node.id === 'latency' ? 'Lat' : node.id}
                                </div>
                              </div>
                            </foreignObject>
                            
                            <text
                              y={node.id === 'git_commit' ? -28 : 34}
                              textAnchor="middle"
                              className="text-[9px] font-bold fill-gray-400 select-none"
                            >
                              {node.label}
                            </text>
                            
                            {node.type === 'variable' && node.status !== 'FALSIFIED' && node.status !== 'falsified' && (
                              <text
                                y="-25"
                                textAnchor="middle"
                                className="text-[9px] font-bold fill-blue-400 font-mono"
                              >
                                {Math.round(node.probability * 100)}%
                              </text>
                            )}
                          </g>
                        );
                      })}
                     </svg>
                   </div>

                   {/* Legend card */}
                   <div className="grid grid-cols-3 gap-4 bg-[#080d16]/30 border border-gray-800/60 rounded-xl p-4 text-xs font-sans">
                     <div>
                       <h4 className="font-bold text-gray-300 mb-1.5 uppercase text-[9px] tracking-wider">Causal Nodes</h4>
                       <div className="space-y-1.5 text-gray-400">
                         <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-amber-500/20 border border-amber-500/60"></span> Change Event (Git Deployment)</div>
                         <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-blue-500/20 border border-blue-500/60"></span> System Variables (Hypotheses)</div>
                         <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-red-500/20 border border-red-500/60"></span> Telemetry Anomaly Target</div>
                       </div>
                     </div>
                     <div>
                       <h4 className="font-bold text-gray-300 mb-1.5 uppercase text-[9px] tracking-wider">Active Probing Links</h4>
                       <div className="space-y-1.5 text-gray-400">
                         <div className="flex items-center gap-1.5"><span className="w-4 h-0.5 border-t-2 border-dashed border-gray-500"></span> Possible: Unproven path</div>
                         <div className="flex items-center gap-1.5"><span className="w-4 h-0.5 border-t-2 border-blue-500"></span> Correlated: Git/Diff timeline matching</div>
                         <div className="flex items-center gap-1.5"><span className="w-4 h-0.5 border-t-2 border-emerald-500"></span> Confirmed: Verified Causal Path</div>
                       </div>
                     </div>
                     <div>
                       <h4 className="font-bold text-gray-300 mb-1.5 uppercase text-[9px] tracking-wider">Bayesian Belief State</h4>
                       <p className="text-gray-400 leading-relaxed text-[11px]">
                         Probabilities represent confidence that the node causes the symptom. Probes reduce entropy until a verified cause stands out.
                       </p>
                     </div>
                   </div>
                 </div>
               );
             })()}

            {/* EVIDENCE TAB */}
            {activeTab === 'evidence' && incidentState && (
              <div className="grid grid-cols-2 gap-4">
                {incidentState.evidence.map((evi) => (
                  <div 
                    key={evi.id} 
                    onClick={() => setSelectedEvidence(evi)}
                    className="glass-panel p-4 rounded-xl border border-gray-800 hover:border-blue-500/40 cursor-pointer hover:shadow-lg hover:shadow-blue-500/5 transition flex flex-col gap-3"
                  >
                    <div className="flex items-center justify-between border-b border-gray-800/40 pb-2">
                      <div className="flex items-center gap-1.5">
                        {evi.evidence_type === 'GIT' ? <GitCommit size={14} className="text-amber-400" /> : <FileText size={14} className="text-blue-400" />}
                        <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">{evi.evidence_type} EVIDENCE</span>
                      </div>
                      <span className="text-[9px] text-gray-500">{new Date(evi.timestamp).toLocaleTimeString()}</span>
                    </div>
                    
                    <div className="text-xs font-bold text-gray-300">Source: {evi.source}</div>
                    <p className="text-xs text-gray-400 line-clamp-3 italic">"{evi.relevance}"</p>
                    
                    <div className="flex items-center justify-between mt-1 text-[10px] font-bold text-gray-500">
                      <span>Reliability: {Math.round(evi.reliability * 100)}%</span>
                      <span className="text-blue-400">View Artifact →</span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* SANDBOX LOGS TAB */}
            {activeTab === 'sandbox' && incidentState && (
              <div className="bg-[#05080e] border border-gray-800 rounded-xl p-4 font-mono text-xs flex flex-col h-[500px]">
                <div className="border-b border-gray-800/80 pb-2 mb-3 flex items-center justify-between text-gray-400 font-bold shrink-0">
                  <div className="flex items-center gap-2">
                    <Terminal size={14} className="text-blue-500" />
                    <span>Sandbox Console Terminal Output</span>
                  </div>
                  <span className="text-[10px] bg-blue-500/10 px-2 py-0.5 rounded text-blue-400 border border-blue-500/25 uppercase tracking-wider">Active</span>
                </div>
                
                <div className="flex-1 overflow-y-auto space-y-1.5 text-gray-300 pr-2">
                  {incidentState.logs.map((log, idx) => (
                    <div key={idx} className="flex gap-2">
                      <span className="text-gray-500 select-none">[{idx+1}]</span>
                      <span className={log.includes("error") || log.includes("failed") || log.includes("Error") ? 'text-red-400' : log.includes("verified") || log.includes("Success") || log.includes("RESOLVED") ? 'text-emerald-400' : 'text-gray-300'}>
                        {log}
                      </span>
                    </div>
                  ))}
                  <div ref={terminalEndRef}></div>
                </div>
              </div>
            )}

            {/* WE WILL WIN FINDINGS TAB */}
            {activeTab === 'findings' && (
              <div className="max-w-6xl mx-auto py-2">
                <div className="mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-800 pb-4">
                  <div>
                    <h3 className="text-base font-bold text-white flex items-center gap-2">
                      <FileText className="text-blue-500" size={18} />
                      Project WE WILL WIN — Findings & Clinical Reports
                    </h3>
                    <p className="text-xs text-gray-400 mt-1">
                      Comprehensive clinical, technical, regulatory, and business strategy files for the NeoGuard Screening platform.
                    </p>
                  </div>
                  <a 
                    href="http://localhost:8080/clinical_dashboard_overview.html" 
                    target="_blank" 
                    rel="noreferrer"
                    className="px-3 py-1.5 text-xs font-bold rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition flex items-center gap-1.5 self-start shrink-0 shadow-lg shadow-blue-500/10"
                  >
                    <Activity size={12} className="animate-pulse" />
                    Open NeoGuard Portal →
                  </a>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                  {/* Left Column: Selector */}
                  <div className="md:col-span-1 flex flex-col gap-2">
                    {[
                      { id: "tech_report", title: "Technical Report", category: "Technical & ML" },
                      { id: "study_protocol", title: "Study Protocol", category: "Clinical" },
                      { id: "hardware_spec", title: "Hardware Spec & BOM", category: "Engineering" },
                      { id: "regulatory_qms", title: "Regulatory & QMS", category: "Regulatory" },
                      { id: "risk_file", title: "Risk Management File", category: "Risk/Safety" },
                      { id: "research_paper", title: "Academic PDF", category: "Research Paper" }
                    ].map(doc => (
                      <button
                        key={doc.id}
                        onClick={() => setSelectedDoc(doc.id)}
                        className={`w-full text-left p-3 rounded-lg border transition text-xs flex flex-col gap-1 ${
                          selectedDoc === doc.id
                            ? 'bg-[#0f172a] border-blue-500/60 text-white'
                            : 'bg-[#090d16]/30 border-gray-800 hover:border-gray-700 text-gray-400'
                        }`}
                      >
                        <span className="font-bold text-gray-200">{doc.title}</span>
                        <span className="text-[10px] text-gray-500">{doc.category}</span>
                      </button>
                    ))}
                  </div>

                  {/* Right Column: Viewer */}
                  <div className="md:col-span-3 bg-[#080c14]/40 border border-gray-800 rounded-xl p-5 flex flex-col gap-5 min-h-[420px]">
                    {(() => {
                      const doc = documentsData[selectedDoc as keyof typeof documentsData];
                      if (!doc) return <div className="text-gray-500 text-xs">Select a document to view findings.</div>;
                      return (
                        <>
                          <div className="flex justify-between items-start border-b border-gray-800/60 pb-3">
                            <div>
                              <h4 className="text-md font-bold text-gray-200">{doc.title}</h4>
                              <p className="text-xs text-gray-400 mt-1">{doc.subtitle}</p>
                              <div className="flex gap-4 mt-2 text-[10px] text-gray-500 font-mono">
                                <span>Author: {doc.author}</span>
                                <span>Date: {doc.date}</span>
                                <span className="text-blue-400 font-semibold">{doc.status}</span>
                              </div>
                            </div>
                            <a
                              href={doc.downloadUrl}
                              download
                              className="px-3 py-1.5 bg-[#0e1629] border border-gray-800 text-gray-300 rounded hover:bg-gray-800 text-xs font-bold transition flex items-center gap-1.5"
                            >
                              Download File
                            </a>
                          </div>

                          <div className="flex flex-col gap-3">
                            <span className="text-[10px] font-bold uppercase text-gray-400 tracking-wider">Key Takeaways & Findings</span>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                              {doc.summary.map((sum, index) => (
                                <div key={index} className="bg-[#0b1324]/30 border border-gray-900 rounded-lg p-3 flex gap-2">
                                  <span className="text-blue-500 text-xs font-bold mt-0.5">•</span>
                                  <span className="text-xs text-gray-300 leading-relaxed">{sum}</span>
                                </div>
                              ))}
                            </div>
                          </div>

                          <div className="flex flex-col gap-2 mt-2">
                            <span className="text-[10px] font-bold uppercase text-gray-400 tracking-wider">Scope & Details</span>
                            <p className="text-xs text-gray-400 leading-relaxed bg-[#05080e] p-3 rounded-lg border border-gray-900 font-mono whitespace-pre-line">
                              {doc.details}
                            </p>
                          </div>

                          {/* Render specific tables/charts for specific documents to make it look premium */}
                          {selectedDoc === "hardware_spec" && (
                            <div className="flex flex-col gap-2 mt-2">
                              <span className="text-[10px] font-bold uppercase text-gray-400 tracking-wider">Parametric Prototype Bill of Materials (BOM)</span>
                              <div className="overflow-x-auto border border-gray-900 rounded-lg">
                                <table className="w-full text-left border-collapse text-[11px]">
                                  <thead>
                                    <tr className="bg-gray-950/60 border-b border-gray-900 text-gray-400">
                                      <th className="p-2 font-bold">Component</th>
                                      <th className="p-2 font-bold">Specification</th>
                                      <th className="p-2 font-bold text-right">Cost (INR)</th>
                                    </tr>
                                  </thead>
                                  <tbody className="divide-y divide-gray-900 text-gray-300">
                                    <tr><td className="p-2 font-semibold">PETG Housing</td><td className="p-2">3D-printed body, disinfectant compatible</td><td className="p-2 text-right">₹220</td></tr>
                                    <tr><td className="p-2 font-semibold">LED Ring</td><td className="p-2">SMD LED Ring, daylight-balanced ~5600K, CRI&gt;90</td><td className="p-2 text-right">₹90</td></tr>
                                    <tr><td className="p-2 font-semibold">Diffuser Film</td><td className="p-2">Light diffusion plate, prevents hot-spot glare</td><td className="p-2 text-right">₹15</td></tr>
                                    <tr><td className="p-2 font-semibold">Calibration Target</td><td className="p-2">Matte card (White, Gray, Black patches)</td><td className="p-2 text-right">₹40</td></tr>
                                    <tr><td className="p-2 font-semibold">Aperture Window</td><td className="p-2">Clear polycarbonate lens, anti-glare coating</td><td className="p-2 text-right">₹35</td></tr>
                                    <tr><td className="p-2 font-semibold">Spring Clip</td><td className="p-2">Adjustable phone mount clip (58-90mm jaw)</td><td className="p-2 text-right">₹60</td></tr>
                                    <tr><td className="p-2 font-semibold">Coin Cell Battery</td><td className="p-2">Li-ion battery + switch (independent power)</td><td className="p-2 text-right">₹50</td></tr>
                                    <tr className="bg-gray-950/30 text-white font-bold"><td className="p-2" colSpan={2}>Total Estimated Prototype Unit Cost (v1)</td><td className="p-2 text-right">₹610</td></tr>
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          )}

                          {selectedDoc === "risk_file" && (
                            <div className="flex flex-col gap-2 mt-2">
                              <span className="text-[10px] font-bold uppercase text-gray-400 tracking-wider">Hazard Identification & Control Triage (ISO 14971)</span>
                              <div className="overflow-x-auto border border-gray-900 rounded-lg">
                                <table className="w-full text-left border-collapse text-[11px]">
                                  <thead>
                                    <tr className="bg-gray-950/60 border-b border-gray-900 text-gray-400">
                                      <th className="p-2 font-bold w-12">ID</th>
                                      <th className="p-2 font-bold">Hazard Description</th>
                                      <th className="p-2 font-bold w-24">Initial Risk</th>
                                      <th className="p-2 font-bold w-32">Residual Status</th>
                                    </tr>
                                  </thead>
                                  <tbody className="divide-y divide-gray-900 text-gray-300">
                                    <tr><td className="p-2 font-semibold text-gray-500">H-2</td><td className="p-2">AI model false negative (underestimates bilirubin)</td><td className="p-2">Critical (15)</td><td className="p-2"><span className="px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/25">ALARP (Controlled)</span></td></tr>
                                    <tr><td className="p-2 font-semibold text-gray-500">H-3</td><td className="p-2">Poor image quality silently accepted (blur, glare)</td><td className="p-2">Moderate (8)</td><td className="p-2"><span className="px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/25">ALARP (Controlled)</span></td></tr>
                                    <tr><td className="p-2 font-semibold text-gray-500">H-4</td><td className="p-2">Color calibration failure (lighting cast)</td><td className="p-2">Moderate (8)</td><td className="p-2"><span className="px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/25">ALARP (Controlled)</span></td></tr>
                                    <tr><td className="p-2 font-semibold text-gray-500">H-5</td><td className="p-2">ROI (sclera/skin) misdetection</td><td className="p-2">Moderate (8)</td><td className="p-2"><span className="px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/25">ALARP (Controlled)</span></td></tr>
                                    <tr><td className="p-2 font-semibold text-gray-500">H-1</td><td className="p-2">Nomogram bilirubin thresholds are unverified</td><td className="p-2">High (20)</td><td className="p-2"><span className="px-1.5 py-0.5 rounded bg-red-500/10 text-red-400 border border-red-500/25">Unacceptable (Block)</span></td></tr>
                                    <tr><td className="p-2 font-semibold text-gray-500">H-6</td><td className="p-2">Model trained/validated only on synthetic data</td><td className="p-2">High (20)</td><td className="p-2"><span className="px-1.5 py-0.5 rounded bg-red-500/10 text-red-400 border border-red-500/25">Unacceptable (Block)</span></td></tr>
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          )}

                          {selectedDoc === "tech_report" && (
                            <div className="flex flex-col gap-2 mt-2">
                              <span className="text-[10px] font-bold uppercase text-gray-400 tracking-wider">Validation Accuracy Metrics (Synthetic vs Real Photos)</span>
                              <div className="grid grid-cols-2 gap-4">
                                <div className="bg-[#0b1324]/30 border border-gray-900 rounded-lg p-3">
                                  <span className="text-xs font-bold text-gray-300 block mb-2">Synthetic Data Model</span>
                                  <div className="space-y-1 text-[11px]">
                                    <div className="flex justify-between"><span>ROC-AUC</span><span className="text-emerald-400 font-bold">95.8%</span></div>
                                    <div className="flex justify-between"><span>Sensitivity (Recall)</span><span className="text-emerald-400 font-bold">80.0%</span></div>
                                    <div className="flex justify-between"><span>Specificity</span><span className="text-emerald-400 font-bold">95.9%</span></div>
                                    <div className="flex justify-between"><span>Mean Absolute Error (MAE)</span><span className="text-gray-300">1.6 mg/dL</span></div>
                                  </div>
                                </div>
                                <div className="bg-[#0b1324]/30 border border-gray-900 rounded-lg p-3">
                                  <span className="text-xs font-bold text-gray-300 block mb-2">Real Photo (Kaggle/NJN) Model</span>
                                  <div className="space-y-1 text-[11px]">
                                    <div className="flex justify-between"><span>Accuracy</span><span className="text-amber-400 font-bold">74.7%</span></div>
                                    <div className="flex justify-between"><span>Sensitivity (Recall)</span><span className="text-amber-400 font-bold">50.0%</span></div>
                                    <div className="flex justify-between"><span>Specificity</span><span className="text-amber-400 font-bold">83.6%</span></div>
                                    <div className="flex justify-between"><span>5-Fold CV Mean Accuracy</span><span className="text-gray-300">73.5%</span></div>
                                  </div>
                                </div>
                              </div>
                            </div>
                          )}
                        </>
                      );
                    })()}
                  </div>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* RIGHT COLUMN: Hypotheses and Actions */}
        <section className="w-[380px] p-5 bg-[#070b13]/40 flex flex-col gap-5 shrink-0 overflow-y-auto">
          
          {/* HYPOTHESIS PROBABILITY CHART */}
          {incidentState && (
            <div className="flex flex-col gap-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400">Competing Hypotheses</h3>
              
              <div className="glass-panel p-4 rounded-xl">
                <div className="h-44 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData} layout="vertical" margin={{ left: -10, right: 10, top: 0, bottom: 0 }}>
                      <XAxis type="number" domain={[0, 100]} hide />
                      <YAxis dataKey="name" type="category" stroke="#9ca3af" fontSize={11} width={25} />
                      <Bar dataKey="probability" radius={[0, 4, 4, 0]} barSize={14}>
                        {chartData.map((entry, index) => {
                          let color = '#3b82f6'; // default active blue
                          if (entry.status === 'VERIFIED') color = '#10b981'; // green
                          if (entry.status === 'FALSIFIED') color = '#ef4444'; // red
                          return <Cell key={`cell-${index}`} fill={color} fillOpacity={0.8} />;
                        })}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                
                {/* Hypothesis Legend list */}
                <div className="space-y-2 mt-4 border-t border-gray-800/40 pt-4">
                  {incidentState.hypotheses.map(h => (
                    <div key={h.id} className="flex justify-between items-start text-xs border-b border-gray-900 pb-2 last:border-0 last:pb-0">
                      <div className="flex flex-col gap-0.5 max-w-[240px]">
                        <span className="font-bold text-gray-300">{h.id}: {h.id === 'H1' ? 'Data Drift' : h.id === 'H2' ? 'Model Version' : h.id === 'H3' ? 'Preprocessing Mismatch' : h.id === 'H4' ? 'Dependency Upgrade' : 'Resource/Config Lock'}</span>
                        <span className="text-[10px] text-gray-500 leading-normal">{h.description}</span>
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        <span className="font-bold text-gray-200">{Math.round(h.probability * 100)}%</span>
                        <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${h.status === 'VERIFIED' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/25' : h.status === 'FALSIFIED' ? 'bg-red-500/10 text-red-400 border border-red-500/25' : 'bg-blue-500/10 text-blue-400 border border-blue-500/25'}`}>
                          {h.status}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* ACTION CENTER */}
          {incidentState && (
            <div className="flex flex-col gap-3">
               <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400">Action Control Center</h3>
              
              <div className="glass-panel p-4 rounded-xl flex flex-col gap-3">
                 <div className="flex items-center gap-2 text-xs font-bold text-gray-300">
                  <Shield size={16} className="text-blue-500" />
                  <span>Security Risk Authorization Gate</span>
                </div>
                
                {incidentState.investigation_status === 'AWAITING_APPROVAL' ? (
                  <div className="bg-amber-500/10 border border-amber-500/35 p-3 rounded-lg flex flex-col gap-3">
                    <div className="text-xs text-amber-400 font-semibold flex items-center gap-1.5 animate-pulse-soft">
                      <ShieldAlert size={14} /> Production Modification Patch Proposed
                    </div>
                    <p className="text-xs text-gray-300 leading-relaxed">
                      The agent has verified the root cause as **{incidentState.confirmed_root_cause}** and generated a Git rollback patch. Human approval is required to apply the fix to the production container.
                    </p>
                    <button 
                      onClick={handleApprovePatch}
                      className="w-full py-2 bg-amber-500 text-gray-950 font-bold rounded-lg text-xs hover:bg-amber-400 transition hover:shadow-lg hover:shadow-amber-500/10"
                    >
                      Approve production Hotfix Patch
                    </button>
                  </div>
                ) : incidentState.investigation_status === 'RESOLVED' ? (
                  <div className="bg-emerald-500/10 border border-emerald-500/30 p-3 rounded-lg flex flex-col gap-2">
                    <div className="text-xs text-emerald-400 font-bold flex items-center gap-1.5">
                      <CheckCircle size={14} /> Service Fully Restored
                    </div>
                    <p className="text-xs text-gray-400 leading-relaxed">
                      The patch has been verified in the sandbox workspace, showing validation parameters restored to baseline. The fix has been deployed, and active telemetry shows healthy metrics.
                    </p>
                  </div>
                ) : (
                  <div className="bg-gray-950/40 border border-gray-800 p-3 rounded-lg flex flex-col gap-2">
                    <div className="text-xs text-gray-400 font-semibold flex items-center gap-1.5">
                      <Cpu size={14} className="animate-spin text-blue-500" />
                      <span>Agent Decision: Running Sandbox Diagnoses</span>
                    </div>
                    <p className="text-xs text-gray-500">
                      Current Action: {incidentState.next_action || 'Determining next investigation step based on Bayesian scores...'}
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* COUNTERFACTUAL VERIFICATION */}
          {incidentState && incidentState.counterfactual_verification && (
            <div className="flex flex-col gap-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400">Counterfactual Verification</h3>
              
              <div className="glass-panel p-4 rounded-xl border border-blue-500/20 bg-blue-950/5 flex flex-col gap-3">
                <div className="flex items-center gap-2 text-xs font-bold text-blue-400">
                  <Activity size={15} className="animate-pulse" />
                  <span>Causal Proof: Counterfactual State Contrast</span>
                </div>
                
                <div className="grid grid-cols-2 gap-2 mt-1">
                  <div className="bg-red-500/5 border border-red-500/15 p-2.5 rounded-lg text-[10px]">
                    <span className="text-red-400 font-bold uppercase block text-[8px] tracking-wider">Real-World State</span>
                    <span className="text-gray-300 block font-semibold truncate mt-0.5">{incidentState.counterfactual_verification.real_world_value}</span>
                    <span className="text-red-400 font-extrabold block text-xs mt-1">{incidentState.counterfactual_verification.real_world_metric}</span>
                  </div>
                  <div className="bg-emerald-500/5 border border-emerald-500/15 p-2.5 rounded-lg text-[10px]">
                    <span className="text-emerald-400 font-bold uppercase block text-[8px] tracking-wider">Counterfactual State</span>
                    <span className="text-gray-300 block font-semibold truncate mt-0.5">{incidentState.counterfactual_verification.counterfactual_value}</span>
                    <span className="text-emerald-400 font-extrabold block text-xs mt-1">{incidentState.counterfactual_verification.counterfactual_metric}</span>
                  </div>
                </div>
                
                <div className="bg-black/35 p-3 rounded-lg border border-gray-800 mt-1">
                  <span className="text-[8px] font-bold text-gray-500 uppercase block tracking-wider font-mono">Causal Proof Explanation</span>
                  <p className="text-xs text-gray-300 italic leading-relaxed mt-1">
                    "{incidentState.counterfactual_verification.proof}"
                  </p>
                </div>
              </div>
            </div>
          )}
        </section>
      </main>

      {/* EVIDENCE DETAIL MODAL */}
      {selectedEvidence && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0b0f19] border border-gray-800 rounded-2xl max-w-2xl w-full p-6 flex flex-col max-h-[85vh]">
            <div className="flex items-center justify-between border-b border-gray-800 pb-3 mb-4">
              <div className="flex items-center gap-2">
                <Database size={16} className="text-blue-500" />
                <h3 className="text-sm font-bold text-gray-200">Evidence ID: {selectedEvidence.id}</h3>
              </div>
              <button onClick={() => setSelectedEvidence(null)} className="text-gray-500 hover:text-gray-300">
                <X size={18} />
              </button>
            </div>
            
            <div className="space-y-4 overflow-y-auto pr-2">
              <div className="grid grid-cols-2 gap-4 text-xs">
                <div>
                  <span className="text-gray-500 font-semibold uppercase block">Source Layer</span>
                  <span className="text-gray-300 font-bold">{selectedEvidence.source}</span>
                </div>
                <div>
                  <span className="text-gray-500 font-semibold uppercase block">Timestamp</span>
                  <span className="text-gray-300">{new Date(selectedEvidence.timestamp).toLocaleString()}</span>
                </div>
              </div>
              
              <div>
                <span className="text-gray-500 font-semibold uppercase text-xs block mb-1">Relevance Explanation</span>
                <p className="text-xs text-gray-300 bg-blue-500/5 border border-blue-500/20 p-3 rounded-lg leading-relaxed">
                  {selectedEvidence.relevance}
                </p>
              </div>

              <div>
                <span className="text-gray-500 font-semibold uppercase text-xs block mb-1.5">Raw Artifact Payload</span>
                <pre className="text-xs bg-[#05080e] border border-gray-800 p-4 rounded-xl text-emerald-400 font-mono overflow-x-auto max-h-72 whitespace-pre-wrap">
                  {selectedEvidence.content}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* WORKSPACE CONNECT MODAL */}
      {showWorkspace && <WorkspacePanel onClose={() => setShowWorkspace(false)} />}
    </div>
  );
}
