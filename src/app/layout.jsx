import "./globals.css";

export const metadata = {
  title: "Chronicle Agentic RAG",
  description: "A production Agentic RAG interface",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
