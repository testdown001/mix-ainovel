// AIMETA P=写作偏好API客户端_风格配置接口|R=写作偏好CRUD|NR=不含UI逻辑|E=api:writingPreferences|X=internal|A=API对象|D=fetch|S=net|RD=./README.ai
import { useAuthStore } from '@/stores/auth';

const API_PREFIX = '/api';
const BASE = `${API_PREFIX}/writing-preferences`;

export interface WritingPreference {
  user_id: number;
  style_preset: string | null;
  custom_rules: string | null;
  banned_phrases: string[] | null;
}

export interface WritingPreferenceCreate {
  style_preset?: string | null;
  custom_rules?: string | null;
  banned_phrases?: string[] | null;
}

export interface PresetInfo {
  key: string;
  name: string;
  description: string;
  banned_phrases: string[];
}

const getHeaders = () => {
  const authStore = useAuthStore();
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${authStore.token}`,
  };
};

export const getWritingPreference = async (): Promise<WritingPreference | null> => {
  const response = await fetch(BASE, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error('Failed to fetch writing preference');
  }
  return response.json();
};

export const saveWritingPreference = async (data: WritingPreferenceCreate): Promise<WritingPreference> => {
  const response = await fetch(BASE, {
    method: 'PUT',
    headers: getHeaders(),
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    throw new Error('Failed to save writing preference');
  }
  return response.json();
};

export const deleteWritingPreference = async (): Promise<void> => {
  const response = await fetch(BASE, {
    method: 'DELETE',
    headers: getHeaders(),
  });
  if (!response.ok) {
    throw new Error('Failed to delete writing preference');
  }
};

export const getPresets = async (): Promise<PresetInfo[]> => {
  const response = await fetch(`${BASE}/presets`, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (!response.ok) {
    throw new Error('Failed to fetch presets');
  }
  return response.json();
};
