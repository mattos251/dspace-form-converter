#!/usr/bin/env python3
"""
Conversor: input-forms.xml (DSpace 5) → item-submission.xml (DSpace 9)

Responsabilidade: Converter apenas o mapeamento e orquestração de processos
- Lê: input-forms.xml (form-map) e submission-forms.xml (para validar formulários)
- Escreve: item-submission.xml (submission-map, step-definitions, submission-processes)

Mudanças aplicadas:
- Converte form-map em submission-map
- Cria step-definitions para cada formulário
- Gera submission-processes orquestrando os passos
- Adiciona passos padrão (collection, upload, license)
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Set, Tuple


class InputSubmissionToItemSubmissionConverter:
    """Converte input-forms.xml para item-submission.xml"""
    
    INDENT = "    "

    # DSpace 9 exige um formulário default no topo do submission-map
    DEFAULT_COLLECTION_HANDLE = "default"
    DEFAULT_FORM_NAME = "td"
    
    # Classes de processamento REST API
    DESCRIBE_STEP_CLASS = "org.dspace.app.rest.submit.step.DescribeStep"
    COLLECTION_STEP_CLASS = "org.dspace.app.rest.submit.step.CollectionStep"
    UPLOAD_STEP_CLASS = "org.dspace.app.rest.submit.step.UploadStep"
    LICENSE_STEP_CLASS = "org.dspace.app.rest.submit.step.LicenseStep"
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.available_forms: Set[str] = set()
        self.collection_mappings: List[Tuple[str, str]] = []
    
    def log(self, message: str, level: str = "INFO") -> None:
        """Log mensagens de conversão"""
        if self.verbose:
            print(f"[{level}] {message}")
    
    def parse_xml_file(self, path: Path) -> ET.Element:
        """Parse arquivo XML"""
        try:
            tree = ET.parse(path)
            return tree.getroot()
        except ET.ParseError as e:
            raise ValueError(f"Erro ao parsear XML: {e}")
    
    def load_available_forms(self, submission_forms_path: Path) -> Set[str]:
        """
        Carrega os nomes dos formulários disponíveis em submission-forms.xml
        Isso garante que só criamos processos para formulários que realmente existem
        """
        self.log(f"Lendo formulários disponíveis de: {submission_forms_path}")
        
        root = self.parse_xml_file(submission_forms_path)
        form_definitions = root.find("form-definitions")
        
        if form_definitions is None:
            raise ValueError("Elemento <form-definitions> não encontrado em submission-forms.xml")
        
        forms = set()
        for form in form_definitions.findall("form"):
            form_name = form.get("name", "").lower()
            if form_name:
                forms.add(form_name)
                self.log(f"  Formulário encontrado: {form_name}")
        
        self.available_forms = forms
        self.log(f"Total de formulários: {len(forms)}")
        return forms
    
    def load_collection_mappings(self, input_forms_path: Path) -> List[Tuple[str, str]]:
        """
        Carrega mapeamentos de collection → formulário de input-forms.xml
        Retorna lista de (collection_handle, form_name)
        """
        self.log(f"Lendo mapeamentos de collection de: {input_forms_path}")
        
        root = self.parse_xml_file(input_forms_path)
        form_map = root.find("form-map")
        
        if form_map is None:
            self.log("Nenhum form-map encontrado", "WARNING")
            return []
        
        mappings = []
        for name_map in form_map.findall("name-map"):
            collection_handle = name_map.get("collection-handle", "")
            form_name = name_map.get("form-name", "").lower()  # Minúsculas!
            
            if collection_handle and form_name:
                mappings.append((collection_handle, form_name))
                self.log(f"  Mapping: {collection_handle} → {form_name}")
        
        self.collection_mappings = mappings
        self.log(f"Total de mapeamentos: {len(mappings)}")
        return mappings
    
    def create_submission_map(self, root: ET.Element) -> ET.Element:
        """
        Cria seção <submission-map> do item-submission.xml
        Converte form-map para submission-map
        """
        self.log("Criando submission-map")
        
        submission_map = ET.SubElement(root, "submission-map")

        # Formulário default sempre no topo (obrigatório no DSpace 9)
        if self.DEFAULT_FORM_NAME in self.available_forms:
            ET.SubElement(
                submission_map,
                "name-map",
                {
                    "collection-handle": self.DEFAULT_COLLECTION_HANDLE,
                    "submission-name": self.DEFAULT_FORM_NAME
                }
            )
            self.log(f"  Adicionado default: {self.DEFAULT_COLLECTION_HANDLE} → {self.DEFAULT_FORM_NAME}")
        else:
            self.log(f"Formulário default '{self.DEFAULT_FORM_NAME}' não existe em submission-forms.xml", "WARNING")
        
        for collection_handle, form_name in self.collection_mappings:
            if collection_handle == self.DEFAULT_COLLECTION_HANDLE:
                continue
            if form_name in self.available_forms:
                # Formulário existe, criar mapping
                mapping = ET.SubElement(
                    submission_map,
                    "name-map",
                    {
                        "collection-handle": collection_handle,
                        "submission-name": form_name
                    }
                )
                self.log(f"  Adicionado mapping: {collection_handle} → {form_name}")
            else:
                # Formulário não existe, adicionar comentário
                comment_text = f' <name-map collection-handle="{collection_handle}" submission-name="{form_name}"/> - formulário não existe na conversão '
                submission_map.append(ET.Comment(comment_text))
                self.log(f"  Formulário não encontrado (comentado): {form_name}", "WARNING")
        
        return submission_map
    
    def add_standard_steps(self, step_definitions: ET.Element) -> None:
        """Adiciona os passos padrão (collection, upload, license)"""
        self.log("Adicionando passos padrão")
        
        # Collection Step
        collection_step = ET.SubElement(
            step_definitions,
            "step-definition",
            {"id": "collection"}
        )
        heading = ET.SubElement(collection_step, "heading")
        heading.text = ""
        proc_class = ET.SubElement(collection_step, "processing-class")
        proc_class.text = self.COLLECTION_STEP_CLASS
        step_type = ET.SubElement(collection_step, "type")
        step_type.text = "collection"
        self.log("  Passo 'collection' adicionado")
        
        # Upload Step
        upload_step = ET.SubElement(
            step_definitions,
            "step-definition",
            {"id": "upload"}
        )
        heading = ET.SubElement(upload_step, "heading")
        heading.text = "submit.progressbar.upload"
        proc_class = ET.SubElement(upload_step, "processing-class")
        proc_class.text = self.UPLOAD_STEP_CLASS
        step_type = ET.SubElement(upload_step, "type")
        step_type.text = "upload"
        self.log("  Passo 'upload' adicionado")
        
        # License Step
        license_step = ET.SubElement(
            step_definitions,
            "step-definition",
            {"id": "license"}
        )
        heading = ET.SubElement(license_step, "heading")
        heading.text = "submit.progressbar.license"
        proc_class = ET.SubElement(license_step, "processing-class")
        proc_class.text = self.LICENSE_STEP_CLASS
        step_type = ET.SubElement(license_step, "type")
        step_type.text = "license"
        scope = ET.SubElement(license_step, "scope", {"visibilityOutside": "read-only"})
        scope.text = "submission"
        self.log("  Passo 'license' adicionado")
    
    def create_step_definitions(self, root: ET.Element) -> ET.Element:
        """
        Cria seção <step-definitions> do item-submission.xml
        Define todos os passos (padrão + um por formulário)
        """
        self.log("Criando step-definitions")
        
        step_definitions = ET.SubElement(root, "step-definitions")
        
        # Adicionar passos padrão
        self.add_standard_steps(step_definitions)
        
        # Adicionar um passo para cada formulário
        for form_name in sorted(self.available_forms):
            step_def = ET.SubElement(
                step_definitions,
                "step-definition",
                {"id": form_name, "mandatory": "true"}
            )
            heading = ET.SubElement(step_def, "heading")
            heading.text = "submit.progressbar.describe.stepone"
            proc_class = ET.SubElement(step_def, "processing-class")
            proc_class.text = self.DESCRIBE_STEP_CLASS
            step_type = ET.SubElement(step_def, "type")
            step_type.text = "submission-form"
            
            self.log(f"  Step-definition criada: {form_name}")
        
        return step_definitions
    
    def create_submission_processes(self, root: ET.Element) -> ET.Element:
        """
        Cria seção <submission-processes> do item-submission.xml
        Orquestra a sequência de passos para cada formulário
        
        Padrão: collection → formulário → upload → license
        """
        self.log("Criando submission-processes")
        
        submission_processes = ET.SubElement(root, "submission-processes")
        
        for form_name in sorted(self.available_forms):
            process = ET.SubElement(
                submission_processes,
                "submission-process",
                {"name": form_name}
            )
            
            # Sequência padrão de passos
            ET.SubElement(process, "step", {"id": "collection"})
            ET.SubElement(process, "step", {"id": form_name})
            ET.SubElement(process, "step", {"id": "upload"})
            ET.SubElement(process, "step", {"id": "license"})
            
            self.log(f"  Submission-process criado: {form_name}")
        
        return submission_processes
    
    def convert(self, 
                submission_forms_path: Path,
                input_forms_path: Path,
                destination_path: Path) -> dict:
        """
        Executa a conversão completa
        
        Args:
            submission_forms_path: Caminho para submission-forms.xml (já convertido)
            input_forms_path: Caminho para input-forms.xml (DSpace 5 original)
            destination_path: Caminho para item-submission.xml (saída)
        
        Returns:
            Dicionário com estatísticas da conversão
        """
        self.log(f"Iniciando conversão de item-submission")
        
        # Carregar formulários disponíveis
        self.load_available_forms(submission_forms_path)
        
        # Carregar mapeamentos de collection
        self.load_collection_mappings(input_forms_path)
        
        # Criar elemento raiz
        root = ET.Element("item-submission")
        
        # Criar submission-map
        self.create_submission_map(root)
        
        # Criar step-definitions
        self.create_step_definitions(root)
        
        # Criar submission-processes
        self.create_submission_processes(root)
        
        # Indentar XML
        self._indent_xml(root)
        
        # Serializar para string
        xml_string = ET.tostring(root, encoding="unicode", short_empty_elements=True)
        
        # Criar conteúdo final com declaração XML e DOCTYPE
        output_content = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<!DOCTYPE item-submission SYSTEM "item-submission.dtd">',
            '',
            xml_string
        ]
        
        # Salvar arquivo
        destination_path.write_text("\n".join(output_content), encoding="utf-8")
        self.log(f"Arquivo salvo: {destination_path}")
        
        # Retornar estatísticas
        stats = {
            "forms_processed": len(self.available_forms),
            "collection_mappings": len(self.collection_mappings),
            "submission_forms_file": str(submission_forms_path),
            "input_forms_file": str(input_forms_path),
            "output_file": str(destination_path),
        }
        
        return stats
    
    def _indent_xml(self, elem: ET.Element, level: int = 0) -> None:
        """Indenta elemento XML recursivamente"""
        indent = "\n" + level * self.INDENT
        
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = indent + self.INDENT
            if not elem.tail or not elem.tail.strip():
                elem.tail = indent
            
            for i, child in enumerate(elem):
                self._indent_xml(child, level + 1)
                if not child.tail or not child.tail.strip():
                    if i == len(elem) - 1:
                        child.tail = indent
                    else:
                        child.tail = indent + self.INDENT
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = indent


def main():
    """Função para testes diretos"""
    import sys
    
    if len(sys.argv) < 4:
        print("Uso: python converter_inputsubmission_to_itemsubmission.py <submission_forms.xml> <input_forms.xml> <output_item_submission.xml>")
        print("\nExemplo:")
        print("  python converter_inputsubmission_to_itemsubmission.py output/submission-forms.xml forms-dspace5/input-forms.xml output/item-submission.xml")
        sys.exit(1)
    
    submission_forms_path = Path(sys.argv[1])
    input_forms_path = Path(sys.argv[2])
    dest_path = Path(sys.argv[3])
    
    converter = InputSubmissionToItemSubmissionConverter(verbose=True)
    stats = converter.convert(submission_forms_path, input_forms_path, dest_path)
    
    print(f"\n{'='*60}")
    print(f"CONVERSÃO CONCLUÍDA!")
    print(f"{'='*60}")
    print(f"Formulários processados: {stats['forms_processed']}")
    print(f"Mapeamentos de collection: {stats['collection_mappings']}")
    print(f"Saída: {stats['output_file']}")


if __name__ == "__main__":
    main()
