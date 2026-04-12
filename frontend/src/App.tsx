import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "@/components/Layout";
import Dashboard from "@/pages/Dashboard";
import Contratacoes from "@/pages/Contratacoes";
import Contratos from "@/pages/Contratos";
import Fornecedores from "@/pages/Fornecedores";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="contratacoes" element={<Contratacoes />} />
          <Route path="contratos" element={<Contratos />} />
          <Route path="fornecedores" element={<Fornecedores />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
