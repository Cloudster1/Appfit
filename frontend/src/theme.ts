import { createTheme, type MantineColorsTuple } from "@mantine/core";

// Cobalt accent of the portal design; index 6 is the filled shade in light mode.
const cobalt: MantineColorsTuple = [
  "#edf1ff",
  "#d9e0fb",
  "#b0bff2",
  "#859beb",
  "#607de4",
  "#4969e0",
  "#2548c9",
  "#1f3db0",
  "#19339a",
  "#102682",
];

const BODY_FONT = "'Instrument Sans Variable', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";
const DISPLAY_FONT = "'Bricolage Grotesque Variable', " + BODY_FONT;

export const theme = createTheme({
  colors: { cobalt },
  primaryColor: "cobalt",
  primaryShade: { light: 6, dark: 5 },
  defaultRadius: "md",
  fontFamily: BODY_FONT,
  fontFamilyMonospace: "ui-monospace, 'SFMono-Regular', Menlo, Consolas, monospace",
  headings: { fontFamily: DISPLAY_FONT, fontWeight: "700" },
  other: { displayFont: DISPLAY_FONT },
});
