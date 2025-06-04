export interface AWSCredentials {
  access_key: string;
  secret_key: string;
  session_token?: string;
  environment: 'com' | 'gov';
}

export interface CredentialValidationResponse {
  success: boolean;
  message: string;
  environment: string;
  expiration?: number;
  expires_in_seconds?: number;
  expires_in_minutes?: number;
  temporary?: boolean;
}

export interface Script {
  id: number;
  name: string;
  content: string;
  description?: string;
  script_type: string;
  tool_id?: number;
}

export interface Execution {
  id: number;
  script_id: number;
  instance_id: number;
  status: 'pending' | 'running' | 'completed' | 'failed';
  start_time: string;
  end_time?: string;
  output?: string;
  exit_code?: number;
  command_id?: string;
}

export interface Instance {
  instance_id: string;
  name?: string;
  platform: string;
  state: string;
  private_ip?: string;
  public_ip?: string;
  tags: Record<string, string>;
}