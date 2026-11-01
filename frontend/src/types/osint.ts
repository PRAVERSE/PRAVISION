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
