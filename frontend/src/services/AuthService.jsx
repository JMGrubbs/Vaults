import { api } from "./api";

export const loginUser = async (email, password) => {
  const response = await api.post("/api/v1/vault/auth/login", {
    email,
    password,
  });
  return response.data;
};

export const registerUser = async (email, password) => {
  const response = await api.post("/api/v1/vault/auth/register", {
    email,
    password,
  });
  return response.data;
};

export const logoutUser = async () => {
  const response = await api.post("/api/v1/vault/auth/logout");
  return response.data;
};
