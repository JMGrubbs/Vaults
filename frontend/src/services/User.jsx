import { api } from "./api";

export const getCurrentUser = async () => {
  const response = await api.get("/api/v1/vault/auth/me");
  return response.data;
};
