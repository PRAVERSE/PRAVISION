export type EntityType = 
  | 'username'
  | 'email'
  | 'phone'
  | 'domain'
  | 'subdomain'
  | 'ip_address'
  | 'url'
  | 'person_name'
  | 'organization'
  | 'image'
  | 'document'
  | 'geo_coordinate'
  | 'location_place'
  | 'hash'
  | 'aircraft'
  | 'vessel'
  | 'technology'
  | 'dns_record'
  | 'breach_record';

export type ConfidenceLevel = 'unverified' | 'low' | 'moderate' | 'high' | 'independently_corroborated';

export type MatchType = 
  | 'exact_match'
  | 'possible_match'
  | 'heuristic_match'
  | 'structural_match'
  | 'contradictory'
  | 'outdated';

export interface EvidenceFinding {
  id: string;
  investigation_id: string;
  entity_type: EntityType;
  entity_value: string;
  source_name: string;
  source_url?: string;
  collection_timestamp: string;
  evidence_description: string;
  match_type: MatchType;
  confidence: ConfidenceLevel;
  verification_status: string;
  limitations?: string;
  related_entities: string[];
  supporting_sources: string[];
  raw_payload: Record<string, any>;
}

export interface GraphNode {
  id: string;
  label: string;
  type: EntityType;
  confidence: ConfidenceLevel;
  properties: Record<string, any>;
  sources: string[];
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relation: string;
  confidence: ConfidenceLevel;
  source_name: string;
  properties: Record<string, any>;
}

export interface IntelligenceGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface ConnectorLiveStatus {
  name: string;
  display_name: string;
  status: 'waiting' | 'running' | 'completed' | 'failed';
  duration_ms: number;
  findings_count: number;
  error_message?: string;
}

export interface ActiveInvestigation {
  id: string;
  root_input: string;
  root_type: EntityType;
  mode: string;
  created_at: string;
  status: 'initialized' | 'running' | 'completed' | 'cancelled' | 'error';
  depth: number;
  total_findings: number;
  verified_relationships: number;
  connector_statuses: Record<string, ConnectorLiveStatus>;
  recent_events: Array<{ type: string; timestamp: string; data: Record<string, any> }>;
}

export interface ConnectorManifest {
  name: string;
  display_name: string;
  category: string;
  description: string;
  website_or_repo: string;
  installed: boolean;
  configured: boolean;
  authenticated: boolean | null;
  health: 'operational' | 'partial' | 'config_required' | 'auth_required' | 'subscription_required' | 'unavailable' | 'restricted';
  capabilities: string[];
  enabled_capabilities: string[];
  restricted_capabilities: string[];
  requires_api_key: boolean;
  is_commercial: boolean;
  last_health_check?: string;
  last_error?: string;
  supported_entity_types: EntityType[];
}

export interface ClassifiedInput {
  raw_value: string;
  detected_type: EntityType;
  mode: string;
  is_valid: boolean;
  recommended_connectors: string[];
  requires_authorization_confirmation: boolean;
  authorization_note?: string;
  expected_scope: string;
}

export interface CaseDossier {
  id: string;
  case_number: string;
  title: string;
  description?: string;
  created_by: string;
  status: 'active' | 'closed' | 'archived' | 'suspended';
  classification: 'UNCLASSIFIED' | 'RESTRICTED' | 'CONFIDENTIAL' | 'SECRET';
  tags: string[];
  created_at: string;
  updated_at?: string;
  investigations?: any[];
  entities_count?: number;
  evidence_count?: number;
}

export interface StorageStatus {
  database: {
    status: string;
    backend: string;
    latency_ms: number;
    is_postgres: boolean;
    error?: string;
  };
  object_storage: {
    b2_cloud_configured: boolean;
    b2_endpoint?: string;
    b2_bucket?: string;
    storage_mode: string;
    local_vault_path: string;
    local_vault_file_count: number;
    local_vault_size_bytes: number;
  };
}

export interface GraphAnalyticsResult {
  nodes_count: number;
  edges_count: number;
  density: number;
  connected_components: number;
  top_entities: Array<{
    id: string;
    label: string;
    type: string;
    degree_centrality: number;
    betweenness_centrality: number;
    pagerank: number;
    community_id: number;
  }>;
  all_metrics: Record<string, any>;
  communities_count: number;
}

export interface TimelineEvent {
  id: string;
  timestamp: string;
  event_type: string;
  entity_value: string;
  source: string;
  confidence: string;
  summary: string;
  raw_metadata: Record<string, any>;
}

export interface TimelineResult {
  total_events: number;
  earliest_event?: string;
  latest_event?: string;
  events: TimelineEvent[];
  detected_bursts: Array<{
    start_time: string;
    event_count: number;
    description: string;
  }>;
}

export interface ThreatPostureResult {
  overall_risk_score: number;
  severity_level: 'BENIGN' | 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL';
  is_known_malicious: boolean;
  indicators: Array<{ type: string; detail: string }>;
  sanctions_matches: Array<{ entity: string; score: number; datasets: string[] }>;
  identified_actors: string[];
  assessment_timestamp: string;
}

export interface AiBriefingResult {
  title: string;
  generated_at: string;
  target: { input: string; type: string };
  metrics: {
    total_findings: number;
    sources_queried: string[];
    graph_nodes: number;
    graph_edges: number;
    high_confidence_findings: number;
  };
  executive_summary: string;
  intelligence_gaps: string[];
  formulated_hypotheses: Array<{ title: string; confidence: string; reasoning: string }>;
  recommended_next_actions: string[];
}


