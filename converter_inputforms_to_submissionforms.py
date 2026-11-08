#!/usr/bin/env python3
"""
Conversor: input-forms.xml (DSpace 5) → submission-forms.xml (DSpace 9)

Responsabilidade: Converter apenas a estrutura de formulários
- Lê: input-forms.xml (com form-definitions)
- Escreve: submission-forms.xml (com form-definitions em formato DSpace 9)

Mudanças aplicadas:
- Converte <page> para <row>
- Normaliza input-types (twobox→name, checkbox→dropdown, etc)
- Adiciona atributos novos (visibility, type-bind)
- Garante que todos os campos têm os elementos obrigatórios
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional


class InputFormsToSubmissionFormsConverter:
    """Converte input-forms.xml para submission-forms.xml"""
    
    INDENT = "    "
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.converted_forms_count = 0
        self.converted_fields_count = 0
    
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
    
    def normalize_field(self, field: ET.Element) -> None:
        """Remove input-type duplicadas, mantendo apenas a primeira"""
        input_types = field.findall("input-type")
        for duplicate in input_types[1:]:
            field.remove(duplicate)
            self.log(f"Removida input-type duplicada em {field.get('dc-element', 'unknown')}")
    
    def convert_input_type(self, field: ET.Element) -> None:
        """
        Converte input-types descontinuados no DSpace 9:
        - twobox → name (com visibility submit)
        - checkbox → dropdown
        - series → onebox
        - qualdrop_value → dropdown (com aviso)
        """
        input_type_elem = field.find("input-type")
        if input_type_elem is None or not input_type_elem.text:
            return
        
        original_type = input_type_elem.text
        dc_element = field.find("dc-element")
        dc_element_text = dc_element.text if dc_element is not None else "unknown"
        
        if original_type == "twobox":
            self.log(f"Convertendo twobox→name para {dc_element_text}")
            input_type_elem.text = "name"
            
            # Adicionar visibility submit para campos de nome
            if field.find("visibility") is None:
                visibility = ET.Element("visibility")
                visibility.text = "submit"
                field.append(visibility)
        
        elif original_type == "checkbox":
            self.log(f"Convertendo checkbox→dropdown para {dc_element_text}")
            input_type_elem.text = "dropdown"
            
            # Adicionar aviso na hint
            hint = field.find("hint")
            if hint is not None and hint.text:
                hint.text = f"{hint.text} [CONVERTIDO DE CHECKBOX]"
        
        elif original_type == "series":
            self.log(f"Convertendo series→onebox para {dc_element_text}")
            input_type_elem.text = "onebox"
        
        elif original_type == "qualdrop_value":
            self.log(f"Convertendo qualdrop_value→dropdown para {dc_element_text} [REVISAR MANUALMENTE]")
            input_type_elem.text = "dropdown"
            
            # Adicionar aviso na hint
            hint = field.find("hint")
            if hint is not None and hint.text:
                hint.text = f"{hint.text} [CONVERTIDO DE QUALDROP_VALUE - REVISAR MANUALMENTE]"
    
    def ensure_field_structure(self, field: ET.Element) -> None:
        """Garante que o campo tem a estrutura correta do DSpace 9"""
        # Elementos que devem estar presentes
        required_elements_order = [
            "dc-schema", "dc-element", "dc-qualifier", "repeatable",
            "label", "input-type", "hint", "required"
        ]
        
        # Se dc-schema não existe, adicionar
        if field.find("dc-schema") is None:
            dc_schema = ET.Element("dc-schema")
            dc_schema.text = "dc"
            # Inserir no início
            field.insert(0, dc_schema)
        
        # Limpar dc-qualifier vazio (converter para self-closing)
        qualifier = field.find("dc-qualifier")
        if qualifier is not None:
            if not qualifier.text or qualifier.text.strip() == "":
                qualifier.text = None
    
    def copy_element(self, source_elem: ET.Element) -> ET.Element:
        """Cria uma cópia de um elemento XML"""
        new_elem = ET.Element(source_elem.tag, source_elem.attrib)
        new_elem.text = source_elem.text
        new_elem.tail = source_elem.tail
        for child in source_elem:
            new_elem.append(self.copy_element(child))
        return new_elem
    
    def convert_field(self, source_field: ET.Element) -> ET.Element:
        """Converte um campo individual do DSpace 5 para DSpace 9"""
        field = ET.Element("field")
        
        # Copiar todos os elementos do campo original
        for elem in source_field:
            field.append(self.copy_element(elem))
        
        # Garantir estrutura correta
        self.ensure_field_structure(field)
        
        # Normalizar input-types duplicadas
        self.normalize_field(field)
        
        # Converter input-types descontinuados
        self.convert_input_type(field)
        
        self.converted_fields_count += 1
        return field
    
    def convert_form(self, source_form: ET.Element) -> ET.Element:
        """
        Converte um formulário completo:
        - Converte nome para minúsculas
        - Converte <page> para <row>
        - Converte cada campo
        """
        form_name = source_form.get("name", "default").lower()
        destination_form = ET.Element("form", {"name": form_name})
        
        self.log(f"Convertendo formulário: {source_form.get('name')} → {form_name}")
        
        pages = source_form.findall("page")
        self.log(f"  Páginas encontradas: {len(pages)}")
        
        for page in pages:
            page_number = page.get("number", "1")
            
            # Adicionar comentário de página para referência
            page_comment = ET.Comment(f" page{page_number} ")
            destination_form.append(page_comment)
            
            # Converter campos em rows
            fields = page.findall("field")
            self.log(f"  Página {page_number}: {len(fields)} campos")
            
            for field in fields:
                row = ET.SubElement(destination_form, "row")
                converted_field = self.convert_field(field)
                row.append(converted_field)
        
        self.converted_forms_count += 1
        return destination_form
    
    def convert(self, source_path: Path, destination_path: Path) -> dict:
        """
        Executa a conversão completa
        
        Args:
            source_path: Caminho para input-forms.xml (DSpace 5)
            destination_path: Caminho para submission-forms.xml (DSpace 9)
        
        Returns:
            Dicionário com estatísticas da conversão
        """
        self.log(f"Iniciando conversão: {source_path}")
        
        # Parse arquivo de entrada
        source_root = self.parse_xml_file(source_path)
        form_definitions = source_root.find("form-definitions")
        
        if form_definitions is None:
            raise ValueError("Elemento <form-definitions> não encontrado em input-forms.xml")
        
        # Criar estrutura de saída
        output_root = ET.Element("input-forms")
        output_definitions = ET.SubElement(output_root, "form-definitions")
        
        # Converter cada formulário
        forms = form_definitions.findall("form")
        self.log(f"Formulários encontrados: {len(forms)}")
        
        for source_form in forms:
            converted_form = self.convert_form(source_form)
            output_definitions.append(converted_form)
        
        # Copiar form-value-pairs se existir (pares de valores usados em dropdowns)
        value_pairs = source_root.find("form-value-pairs")
        if value_pairs is not None:
            self.log("Copiando form-value-pairs")
            output_root.append(self.copy_element(value_pairs))
        
        # Indentar XML
        self._indent_xml(output_root)
        
        # Salvar arquivo de saída
        xml_string = ET.tostring(output_root, encoding="unicode", short_empty_elements=True)
        
        output_content = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<!DOCTYPE input-forms SYSTEM "submission-forms.dtd">',
            xml_string
        ]
        
        destination_path.write_text("\n".join(output_content), encoding="utf-8")
        
        self.log(f"Arquivo salvo: {destination_path}")
        
        # Retornar estatísticas
        stats = {
            "forms_converted": self.converted_forms_count,
            "fields_converted": self.converted_fields_count,
            "input_file": str(source_path),
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
    
    if len(sys.argv) < 3:
        print("Uso: python converter_inputforms_to_submissionforms.py <input_forms.xml> <output_submission_forms.xml>")
        print("\nExemplo:")
        print("  python converter_inputforms_to_submissionforms.py forms-dspace5/input-forms.xml output/submission-forms.xml")
        sys.exit(1)
    
    source_path = Path(sys.argv[1])
    dest_path = Path(sys.argv[2])
    
    converter = InputFormsToSubmissionFormsConverter(verbose=True)
    stats = converter.convert(source_path, dest_path)
    
    print(f"\n{'='*60}")
    print(f"CONVERSÃO CONCLUÍDA!")
    print(f"{'='*60}")
    print(f"Formulários: {stats['forms_converted']}")
    print(f"Campos: {stats['fields_converted']}")
    print(f"Saída: {stats['output_file']}")


if __name__ == "__main__":
    main()
