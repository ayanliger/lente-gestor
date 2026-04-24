import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "@/components/Layout";
import Arrecadacao from "@/pages/Arrecadacao";
import Assistente from "@/pages/Assistente";
import Dashboard from "@/pages/Dashboard";
import Contratacoes from "@/pages/Contratacoes";
import Contratos from "@/pages/Contratos";
import Fornecedores from "@/pages/Fornecedores";
import IndicadoresLRF from "@/pages/IndicadoresLRF";
import Orcamento from "@/pages/Orcamento";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="assistente" element={<Assistente />} />
          <Route path="orcamento" element={<Orcamento />} />
          <Route path="arrecadacao" element={<Arrecadacao />} />
          <Route path="lrf" element={<IndicadoresLRF />} />
          <Route path="contratacoes" element={<Contratacoes />} />
          <Route path="contratos" element={<Contratos />} />
          <Route path="fornecedores" element={<Fornecedores />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
