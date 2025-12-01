/**
 * UI Store
 * ============================================================
 * Global UI state management
 */

import { createSignal } from "solid-js";

// Sidebar state
const [sidebarOpen, setSidebarOpen] = createSignal(true);
const [sidebarCollapsed, setSidebarCollapsed] = createSignal(false);

// Theme
const [theme, setTheme] = createSignal<"dark" | "light">("dark");

// Modal state
const [modalOpen, setModalOpen] = createSignal(false);
const [modalContent, setModalContent] = createSignal<any>(null);

// Toast notifications
export interface Toast {
  id: string;
  type: "success" | "error" | "warning" | "info";
  message: string;
  duration?: number;
}

const [toasts, setToasts] = createSignal<Toast[]>([]);

export function addToast(toast: Omit<Toast, "id">) {
  const id = Math.random().toString(36).slice(2);
  const newToast = { ...toast, id };
  setToasts((prev) => [...prev, newToast]);
  
  // Auto-remove after duration
  setTimeout(() => {
    removeToast(id);
  }, toast.duration || 5000);
  
  return id;
}

export function removeToast(id: string) {
  setToasts((prev) => prev.filter((t) => t.id !== id));
}

// Loading state
const [isLoading, setIsLoading] = createSignal(false);
const [loadingMessage, setLoadingMessage] = createSignal("");

export function showLoading(message = "Carregando...") {
  setIsLoading(true);
  setLoadingMessage(message);
}

export function hideLoading() {
  setIsLoading(false);
  setLoadingMessage("");
}

// Export store
export const uiStore = {
  // Sidebar
  sidebarOpen,
  setSidebarOpen,
  sidebarCollapsed,
  setSidebarCollapsed,
  toggleSidebar: () => setSidebarOpen((prev) => !prev),
  
  // Theme
  theme,
  setTheme,
  toggleTheme: () => setTheme((prev) => (prev === "dark" ? "light" : "dark")),
  
  // Modal
  modalOpen,
  setModalOpen,
  modalContent,
  setModalContent,
  openModal: (content: any) => {
    setModalContent(content);
    setModalOpen(true);
  },
  closeModal: () => {
    setModalOpen(false);
    setModalContent(null);
  },
  
  // Toasts
  toasts,
  addToast,
  removeToast,
  
  // Loading
  isLoading,
  loadingMessage,
  showLoading,
  hideLoading,
};

export default uiStore;


