export type Dimension = "crime" | "green" | "nightlife" | "transport" | "rent";
export type Allocation = Record<Dimension, number>;

export const DIMENSIONS: {
  key: Dimension;
  label: string;
  hint: string;
  color: string;
}[] = [
  { key: "crime", label: "Safety", hint: "Fewer reported crimes nearby", color: "var(--line-safety)" },
  { key: "green", label: "Green space", hint: "Parks, grass and woodland within 800 m", color: "var(--line-green)" },
  { key: "nightlife", label: "Nightlife", hint: "Pubs, bars and restaurants within 800 m", color: "var(--line-nightlife)" },
  { key: "transport", label: "Transport", hint: "Stops and lines within reach", color: "var(--line-transport)" },
  { key: "rent", label: "Affordability", hint: "Lower median private rent", color: "var(--line-rent)" },
];

export const EMPTY_ALLOCATION: Allocation = { crime: 0, green: 0, nightlife: 0, transport: 0, rent: 0 };

export const PRESETS: { name: string; allocation: Allocation }[] = [
  { name: "Young professional", allocation: { crime: 10, green: 10, nightlife: 35, transport: 35, rent: 10 } },
  { name: "Family", allocation: { crime: 35, green: 30, nightlife: 0, transport: 15, rent: 20 } },
  { name: "Budget first", allocation: { crime: 15, green: 10, nightlife: 5, transport: 20, rent: 50 } },
  { name: "Balanced", allocation: { crime: 20, green: 20, nightlife: 20, transport: 20, rent: 20 } },
];

export const total = (a: Allocation) => Object.values(a).reduce((s, v) => s + v, 0);

export const labelFor = (key: string) => DIMENSIONS.find((d) => d.key === key)?.label ?? key;
