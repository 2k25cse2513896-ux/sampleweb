import { create } from "zustand";
import type { Product } from "./api";

export interface CartItem { product: Product; qty: number; }
interface Store { cart: CartItem[]; alertIds: number[]; wishlist: Product[]; add: (product: Product) => void; requestAlert: (id: number) => void; toggleWishlist: (product: Product) => void; remove: (id: number) => void; setQty: (id: number, qty: number) => void; clear: () => void; }

function initialCart(): CartItem[] {
  const raw = localStorage.getItem("tech-toys-cart");
  if (!raw) return [];
  try { return JSON.parse(raw) as CartItem[]; } catch { return []; }
}

function initialWishlist(): Product[] {
  const raw = localStorage.getItem("tech-toys-wishlist");
  if (!raw) return [];
  try { return JSON.parse(raw) as Product[]; } catch { return []; }
}

export const useStore = create<Store>((set) => ({
  cart: initialCart(),
  alertIds: (() => { try { return JSON.parse(localStorage.getItem("tech-toys-alerts") || "[]") as number[]; } catch { return []; } })(),
  wishlist: initialWishlist(),
  add: (product) => set((state) => {
    const found = state.cart.find((item) => item.product.id === product.id);
    let cart: CartItem[];
    if (found) cart = state.cart.map((item) => item.product.id === product.id ? { ...item, qty: item.qty + 1 } : item);
    else cart = [...state.cart, { product, qty: 1 }];
    localStorage.setItem("tech-toys-cart", JSON.stringify(cart));
    return { cart };
  }),
  requestAlert: (id) => set((state) => { const alertIds = state.alertIds.includes(id) ? state.alertIds : [...state.alertIds, id]; localStorage.setItem("tech-toys-alerts", JSON.stringify(alertIds)); return { alertIds }; }),
  toggleWishlist: (product) => set((state) => {
    const exists = state.wishlist.some((item) => item.id === product.id);
    const wishlist = exists ? state.wishlist.filter((item) => item.id !== product.id) : [...state.wishlist, product];
    localStorage.setItem("tech-toys-wishlist", JSON.stringify(wishlist));
    return { wishlist };
  }),
  remove: (id) => set((state) => { const cart = state.cart.filter((item) => item.product.id !== id); localStorage.setItem("tech-toys-cart", JSON.stringify(cart)); return { cart }; }),
  setQty: (id, qty) => set((state) => { const cart = state.cart.map((item) => item.product.id === id ? { ...item, qty: Math.max(1, qty) } : item); localStorage.setItem("tech-toys-cart", JSON.stringify(cart)); return { cart }; }),
  clear: () => { localStorage.removeItem("tech-toys-cart"); set({ cart: [] }); },
}));
