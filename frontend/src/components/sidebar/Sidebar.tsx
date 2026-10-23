import {
  Shield,
  LayoutGrid,
  Eye,
  Play,
  Lock,
  Database,
  Layers,
  BarChart3,
  ChevronRight,
} from 'lucide-react';

type Page = 'overview' | 'evidence' | 'replay' | 'policy' | 'sources' | 'patterns' | 'benchmark';

interface SidebarProps {
  currentPage: Page;
  onNavigate: (p: Page) => void;
}

const navItems: { id: Page; label: string; icon: React.ReactNode }[] = [
  { id: 'overview',  label: 'Overview',          icon: <LayoutGrid size={14} /> },
  { id: 'evidence',  label: 'Evidence Lens',      icon: <Eye size={14} /> },
  { id: 'replay',    label: 'Decision Replay',    icon: <Play size={14} /> },
  { id: 'policy',    label: 'Policy Guard',       icon: <Lock size={14} /> },
  { id: 'sources',   label: 'Evidence Sources',   icon: <Database size={14} /> },
  { id: 'patterns',  label: 'Decision Patterns',  icon: <Layers size={14} /> },
  { id: 'benchmark', label: 'Benchmark',          icon: <BarChart3 size={14} /> },
];

export default function Sidebar({ currentPage, onNavigate }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">
          <Shield size={16} />
        </div>
        <div className="sidebar-logo-text">
          <span className="sidebar-logo-name">ContextFuse</span>
          <span className="sidebar-logo-tag">Context Safety Gate</span>
        </div>
      </div>

      <nav className="sidebar-nav">
        <span className="nav-section-label">Navigation</span>
        {navItems.map(item => (
          <button
            key={item.id}
            className={`nav-item${currentPage === item.id ? ' active' : ''}`}
            onClick={() => onNavigate(item.id)}
          >
            {item.icon}
            {item.label}
            {currentPage === item.id && (
              <ChevronRight size={12} style={{ marginLeft: 'auto', opacity: 0.6 }} />
            )}
          </button>
        ))}
      </nav>

      <div className="sidebar-footer">
        <span className="env-badge">
          <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'currentColor', display: 'inline-block' }} />
          Simulation Mode
        </span>
      </div>
    </aside>
  );
}
