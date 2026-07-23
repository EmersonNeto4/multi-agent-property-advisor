from typing import Optional
from pydantic import BaseModel, Field

class UserPreferences(BaseModel):

    """
    Estrutura que representa as preferências extraídas do pedido do utilizador.
    Todos os campos são opcionais - apenas o que o utilizador mencionar é preenchido.
    """
     
    # Critérios Financeiros
    budget: Optional[float] = Field(
        None, 
        description="Orçamento máximo em euros"
    )
    
    # Características Físicas do Imóvel
    rooms: Optional[int] = Field(
        None, 
        description="Número de quartos desejado (ex: T2 = 2 quartos)"
    )
    
    bathrooms: Optional[int] = Field(
        None, 
        description="Número de casas de banho"
    )
    
    area_m2: Optional[float] = Field(
        None, 
        description="Área mínima em metros quadrados"
    )

    operation: Optional[str] = Field(None, description="Tipo de operação: sale ou rent")
    
    property_type: Optional[str] = Field(
        None, 
        description="Tipo de imóvel (apartamento, moradia, estúdio, etc)"
    )
    
    # Características Extras
    parking: Optional[bool] = Field(
        None, 
        description="Se necessita garagem ou estacionamento"
    )

    pool: Optional[bool] = Field(
        None,
        description="Se deseja piscina"
    )
    
    outdoor_space: Optional[bool] = Field(
        None, 
        description="Se deseja terraço, varanda ou jardim"
    )
    
    # Localização e Ambiente
    location: Optional[str] = Field(
        None, 
        description="Localização específica mencionada (cidade, bairro, região)"
    )
    
    environment_type: Optional[str] = Field(
        None, 
        description="Tipo de ambiente desejado (ex: tranquilo, vibrante, familiar, perto da natureza)"
    )
    
    proximity_services: Optional[str] = Field(
        None, 
        description="Serviços ou locais que devem estar próximos (escolas, metro, praia, etc)"
    )
    
    # Controlo de Fluxo
    skip_location_agent: bool = Field(
        default=False,
        description="True se a localização é específica o suficiente para saltar o Location Agent"
    )
    
    # Informação Adicional
    additional_notes: Optional[str] = Field(
        None,
        description="Quaisquer outras preferências ou requisitos mencionados pelo utilizador"
    )