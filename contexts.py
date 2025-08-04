from typing import Any, Dict, Optional
from kerykeion.relationship_score import RelationshipScore
from astrology import create_astrological_subject, generate_birth_chart, generate_transits
from models import AnalysisRequest, BirthData, CurrentLocation, HoroscopeRequest, PersonalityAnalysis, RelationshipAnalysis, RelationshipAnalysis, RelationshipAnalysisRequest
from config import get_logger
from kerykeion import SynastryAspects
import json

logger = get_logger(__name__)

def build_personality_context(
	request: AnalysisRequest
) -> str:
    
	birth_data = BirthData(
		birth_date=request.birth_date,
		birth_time=request.birth_time,
		latitude=request.latitude,
		longitude=request.longitude
	)
     
	chart = generate_birth_chart(birth_data)
     
	context = """
Your task is to analyze a birth chart and provide insights into the individual's personality, strengths, challenges, and life path. You
will be given a birth chart with planetary positions and aspects. Use this information to create a
comprehensive astrological analysis.

Here is the birth chart you will be analyzing:

<birth_chart>
{BIRTH_CHART}
</birth_chart>

Analyze the birth chart carefully, paying attention to the following elements:
1. Sun sign and its house position
2. Moon sign and its house position
3. Ascendant (Rising sign)
4. Positions of other planets (Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto)
5. Important aspects between planets
6. Any significant patterns or configurations (e.g., Grand Trines, T-Squares)

Based on your analysis, provide insights into the individual's:
1. Core personality traits
2. Emotional nature
3. Communication style
4. Relationships and love life
5. Career and life purpose
6. Strengths and talents
7. Challenges and areas for growth
8. Overall life path and potential

Structure your response as follows:

<analysis>
<overview>
Provide a brief overview of the most prominent features of the birth chart and their general
influence on the individual's personality.
</overview>

<personality_traits>
Discuss the core personality traits, focusing on the Sun sign, Moon sign, and Ascendant. Explain how
these elements interact to shape the individual's character.
</personality_traits>

<emotional_nature>
Analyze the Moon sign and its aspects to describe the person's emotional tendencies and needs.
</emotional_nature>

<communication_and_intellect>
Examine Mercury's position and aspects to provide insights into the individual's communication style
and intellectual approach.
</communication_and_intellect>

<relationships_and_love>
Look at Venus and Mars placements to discuss the person's approach to relationships and romantic
life.
</relationships_and_love>

<career_and_purpose>
Analyze the Midheaven, 10th house, and any relevant planetary placements to provide insights into
career path and life purpose.
</career_and_purpose>

<strengths_and_challenges>
Identify key strengths and potential challenges based on the overall chart analysis.
</strengths_and_challenges>

<life_path>
Synthesize the information to provide an overview of the individual's potential life path and areas
for personal growth.
</life_path>
</analysis>

Remember to use astrological terminology accurately but also explain concepts in a way that someone
with basic astrological knowledge can understand. Provide a balanced view, highlighting both
positive attributes and potential challenges. Avoid making absolute predictions; instead, focus on
tendencies and potentials.

<formatting>
Output your analysis in pure JSON structure:
{{
	"overview": string,
	"personality_traits": {{
		"description": string,
		"key_traits": list,
	}},
	"emotional_nature": {{
		"description": string,
		"emotional_characteristics": list,
	}},
	"communication_and_intellect": {{
		"description": string,
		"communication_strengths": list,
	}},
	"relationships_and_love": {{
		"description": string,
		"relationship_dynamics": list,
	}},
	"career_and_purpose": {{
		"description": string,
		"career_potential": list,
	}},
	"strengths_and_challenges": {{
		"strengths": list,
		"challenges": list,
	}},
	"life_path": {{
		"overview": string,
		"key_development_areas": list,
	}}
}}
</formatting>
"""
	return context.format(BIRTH_CHART=chart.to_string())

def parse_personality_response(response: str) -> PersonalityAnalysis:
	"""Parse the structured analysis response from Claude.
	
	Args:
		response: The raw response string from Claude API.
		
	Returns:
		PersonalityAnalysis: Parsed analysis content.

	Raises:
		ValueError: If the response format is invalid or parsing fails.
	"""
	interpolated_response = "{" + response
	try:
		json_data = json.loads(interpolated_response)
		return PersonalityAnalysis(**json_data)
	except json.JSONDecodeError as e:
		logger.error(f"Failed to parse personality analysis response: {e}")
		raise ValueError("Invalid response format") from e
	except Exception as e:
		logger.error(f"Unexpected error while parsing personality analysis response: {e}")
		raise ValueError("Error processing personality analysis response") from e

def get_compatibility_level(score: int) -> str:
    """Get compatibility level based on Discepolo method ranges."""
    if score <= 5:
        return "Minimal relationship"
    elif score <= 10:
        return "Medium relationship"
    elif score <= 15:
        return "Important relationship"
    elif score <= 20:
        return "Very important relationship"
    elif score <= 35:
        return "Exceptional relationship"
    else:
        return "Rare Exceptional relationship"

def build_horoscope_context(
	request: HoroscopeRequest
) -> str:
	"""Build context for the horoscope request
	
	Args:
		request: HoroscopeRequest containing birth data and current location.
	
	Returns:
		Tuple of (context, transit_chart_str) where:
		- context: Context string for Claude API
		- transit_chart_str: String representation of the transit chart
		- horoscope_type: Either daily, weekly or monthly
	"""

	user = create_astrological_subject(request.birth_data)
	transits = generate_transits(request.current_location, request.horoscope_type)
	aspects = [SynastryAspects(user, transit) for transit in transits]
	aspects = [(transits[idx].iso_formatted_utc_datetime, [aspect.values() for aspect in transit.active_aspects]) for idx, transit in enumerate(aspects)]

	context = """
You are an expert astrologer tasked with creating a personalized horoscope for the next {HOROSCOPE_TYPE}. 
You will use the provided astrological data to craft an insightful and personalized horoscope. 

Follow these instructions carefully:

1. Review the astrological data:

<astrology_aspects>
{ASTROLOGY_ASPECTS}
</astrology_aspects>

2. Interpret the astrological data:
- Analyze the aspects for each one of the time periods.
- Consider the synastry between the user's chart and the transit of planets.
- Identify the most influential aspects and planetary positions for each period.

3. Craft the horoscope:
- Begin with a general overview of the day's energy.
- Focus on the specific areas of life relevant to a {HOROSCOPE_TYPE} horoscope.
- Provide insights, advice, and potential challenges based on the astrological data.
- Use a tone that is encouraging and empowering, while also being realistic.
- Tailor the language to be accessible to those with a basic understanding of astrology.

4. Structure your horoscope:
- Write 3-5 paragraphs, each focusing on a different aspect or area of life.
- Include specific references to planetary positions and aspects without being overly technical.
- Conclude with a summary or key takeaway for the day.

5. Output your horoscope:
- Begin your response with <horoscope> and end it with </horoscope>.
- Within the horoscope tags, use <overview>, <body>, and <conclusion> tags to structure your
content.

Remember to maintain a balance between specificity (based on the astrological data) and general
applicability. Your horoscope should feel personal and insightful while remaining broad enough to
resonate with a wide audience.
"""

	return context.format(HOROSCOPE_TYPE=request.horoscope_type.value, ASTROLOGY_ASPECTS=aspects)

def build_relationship_context(
	request: RelationshipAnalysisRequest
) -> str:
	"""Build context for relationship analysis request.
	
	Args:
		request: RelationshipAnalysisRequest containing birth data for both individuals.
		
	Returns:
		Tuple of (context, birth_chart_str) where:
		- context: Context string for Claude API
		- birth_chart_str: String representation of the birth chart
	"""

	relationship_type = request.relationship_type
	if relationship_type not in ["romantic", "friendship", "professional"]:
		raise ValueError("Invalid relationship type. Must be one of: romantic, friendship, professional.")
	person1 = create_astrological_subject(request.person1_birth_data, "Person1")
	person2 = create_astrological_subject(request.person2_birth_data, "Person2")
	# Use RelationshipScoreFactory for comprehensive analysis
	score_result = RelationshipScore(person1, person2)

	birth_chart_A = generate_birth_chart(request.person1_birth_data, with_svg=False)
	birth_chart_B = generate_birth_chart(request.person2_birth_data, with_svg=False)
	
	# Extract comprehensive information
	result = {
		"total_score": score_result.score,
		"compatibility_level": get_compatibility_level(score_result.score),
		"is_destiny_sign": score_result.is_destiny_sign,
		"relationship_score_aspects": score_result.relevant_aspects
	}
	
	# Format aspects as meaningful strings
	formatted_aspects = []
	for aspect in score_result.relevant_aspects:
		if isinstance(aspect, dict):
			# Create a meaningful string representation: "Sun square Moon (4 points)"
			aspect_str = f"{aspect['p1_name']} {aspect['aspect']} {aspect['p2_name']} ({aspect['points']} points)"
			formatted_aspects.append(aspect_str)
		else:
			# Fallback for non-dict aspects
			formatted_aspects.append(str(aspect))
	
	# Update the result with formatted aspects
	result["formatted_aspects"] = formatted_aspects

	context = """
You are an AI assistant trained in astrology and astronomy. Your task is to analyze the relationship compatibility between two individuals based on their birth charts. 
This relationship type can be romantic, friendship or professional. You will be provided with the relationship type.
You will also be provided with a relationship score, information about destiny signs, a list of astrological aspects contributing to the score and each person's birth chart information.
Use this information to create a comprehensive astrological analysis of their relationship compatibility.
Here is the relationship score and destiny sign information:
<relationship_type>
{RELATIONSHIP_TYPE}
</relationship_type>
<relationship_info>
{SCORE}
{COMPATIBILITY_LEVEL}
{IS_DESTINY_SIGN}
</relationship_info>

The following aspects contribute to the relationship score:
<score_aspects>
{SCORE_ASPECTS}
</score_aspects>

Here are the birth chart details for both individuals:
<birth_chart_A>
{BIRTH_CHART_A}
</birth_chart_A>
<birth_chart_B>
{BIRTH_CHART_B}
</birth_chart_B>

Analyze the compatibility based on the provided information. Consider the following in your analysis:
1. The overall relationship score and its significance
2. The presence or absence of destiny signs and their impact
3. The specific aspects contributing to the score, focusing on:
   a. Sun-Sun aspects
   b. Sun-Moon aspects
   c. Aspects between Sun, Ascendant, and Moon
   d. Venus-Mars aspects
4. The balance of positive and challenging aspects
5. The potential strengths and areas of growth in the relationship

Provide a detailed interpretation of how these factors influence the relationship dynamics, potential challenges, and areas of harmony between the two individuals.
For your reference, this is how the relationship score is calculated:
<relationship_score_rules>
- 8 punti se il Sole di A è in quadratura o in opposizione al Sole di B (11 punti se l'aspetto è entro 2 gradi).
- 8 punti se il Sole di A è congiunto alla Luna di B, o viceversa (11 punti se la congiunzione è entro 2 gradi).
- 4 punti per ogni aspetto che leghi il Sole, l'Ascendente o la Luna di A con il Sole, l'Ascendente o la Luna di B.
- 5 punti se ci troviamo di fronte a due segni di destino.
Per "segni di destino" intendiamo lo stesso segno solare del soggetto, oppure il segno solare opposto, oppure i due segni solari a 90 gradi. Per esempio, per lo Scorpione, i 4 segni di destino sono: Scorpione, Toro, Leone e Aquario. Per la Bilancia sono: Bilancia, Ariete, Cancro e Capricorno. Nella nostra esperienza questi quattro segni hanno una grande importanza nel destino di ciascuno, soprattutto nel destino delle coppie. Se vi è, nel caso analizzato, un aspetto preciso di quadratura o di opposizione, allora questi 5 punti non vengono assegnati.
- 4 punti se c'è un aspetto tra Venere di A e Marte di B o viceversa. Anche se il rapporto in gioco non è propriamente di tipo sessuale, tuttavia il richiamo Venere-Marte gioca comunque un ruolo importante nella sinastria.
</relationship_score_rules>

Structure your response as follows:
<analysis>
<overview>
The overall relationship score and its significance
</overview>
<compatibility_level>
Discuss the compatibility level based on the score and its implications for the relationship.
</compatibility_level>
<destiny_signs>
The presence or absence of destiny signs and their impact
</destiny_signs>
<relationship_aspects>
Discuss the key astrological aspects contributing to the relationship score.
</relationship_aspects>
<strengths>
Identify the strengths of the relationship based on the analysis.
</strengths>
<challenges>
Identify the challenges or potential areas of conflict in the relationship.
</challenges>
<areas_for_growth>
Potential areas for growth for the couple based on the astrological analysis.
</areas_for_growth>
</analysis>

<formatting>
Output your analysis in pure JSON structure:
{{
	"score": int,
	"overview": string,
	"compatibility_level": string,
	"destiny_signs": string,
	"relationship_aspects": list,
	"strengths": list,
	"challenges": list,
	"areas_for_growth": list
}}
</formatting>
"""

	return context.format(
		RELATIONSHIP_TYPE=relationship_type,
		SCORE=result['total_score'],
		COMPATIBILITY_LEVEL=result['compatibility_level'],
		IS_DESTINY_SIGN="Yes" if result['is_destiny_sign'] else "No",
		SCORE_ASPECTS=", ".join(result['formatted_aspects']),
		BIRTH_CHART_A=birth_chart_A.to_string(),
		BIRTH_CHART_B=birth_chart_B.to_string()
	)

def parse_relationship_response(response: str) -> RelationshipAnalysis:
	"""Parse the structured relationship analysis response from Claude.
	
	Args:
		response: The raw response string from Claude API.
		
	Returns:
		RelationshipAnalysis: Parsed analysis content.
		
	Raises:
		ValueError: If the response format is invalid or parsing fails.
	"""
	interpolated_response = "{" + response
	try:
		json_data = json.loads(interpolated_response)
		return RelationshipAnalysis(**json_data)
	except json.JSONDecodeError as e:
		logger.error(f"Failed to parse personality analysis response: {e}")
		raise ValueError("Invalid response format") from e
	except Exception as e:
		logger.error(f"Unexpected error while parsing personality analysis response: {e}")
		raise ValueError("Error processing personality analysis response") from e

def build_chat_context(context_data: Optional[Dict[str, str]] = None) -> str:
    """Build the system context for Claude chat.
    
    Args:
        context_data: Optional astrological context data
        
    Returns:
        Complete context string for Claude
    """
    context = (
        "You are a knowledgeable and friendly astrologer. Engage in natural conversation with the user. "
        "Respond to greetings, casual questions, and general chat normally without forcing astrological content. "
        "Only provide astrological insights when the user specifically asks about:\n"
        "- Life advice, guidance, or personal growth\n"
        "- Career, relationships, or future planning\n"
        "- Astrological topics, birth charts, or planetary influences\n"
        "- Current life situations where cosmic guidance would be helpful\n\n"
    )
    
    if context_data:
        context += (
            "ASTROLOGICAL DATA AVAILABLE (only reference when relevant to the user's question):\n"
            f"Birth Chart: {context_data['birth_chart']}\n"
            f"Current Planetary Positions: {context_data['current_data']}\n\n"
            "Only reference this astrological data when the user's question specifically relates to astrology, "
            "personal guidance, life advice, or cosmic influences. For casual conversation, greetings, or "
            "general questions, respond naturally without mentioning charts or planetary positions.\n\n"
        )
    
    context += (
        "IMPORTANT: Always respond in plain text, never JSON format. "
        "Be conversational, warm, and authentic. Match the user's energy - if they're casual, be casual. "
        "If they're seeking deep guidance, provide thoughtful astrological insights."
    )
    
    return context