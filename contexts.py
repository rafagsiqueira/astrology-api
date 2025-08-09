from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from astrology import create_astrological_subject, generate_birth_chart, generate_composite_chart, subject_to_chart
from models import AnalysisRequest, AstrologicalChart, BirthData, ChartAnalysis, ChatMessage, CurrentLocation, DailyTransit, HoroscopePeriod, HoroscopeRequest, PersonalityAnalysis, RelationshipAnalysis, RelationshipAnalysis, RelationshipAnalysisRequest, CompositeAnalysisRequest, CompositeAnalysis, DailyTransitResponse, DailyHoroscopeResponse
from config import get_claude_client, get_logger
from kerykeion import SynastryAspects
from kerykeion.kr_types.kr_models import RelationshipScoreModel, TransitsTimeRangeModel   
import json

logger = get_logger(__name__)

def build_birth_chart_context(
	subject: AstrologicalChart
) -> tuple[str, str]:
	
	system: str = """
	You are an expert astrologer tasked with interpreting a person's astrological chart based on the
	positions of celestial bodies in different houses. You will receive a list of planets (including the
	Sun and Moon) and their corresponding houses. Your job is to explain what it means for each
	celestial body to be in its particular house and how it affects someone's personality.

	For each planet-house combination in the list:

	1. Describe how this placement influences the person's personality, behaviors, and life experiences.
	2. Provide at least three specific traits or tendencies associated with this placement.

	Present your interpretation for each planet-house combination in the following format:

	<interpretation>
	<planet_house>[Planet] in [House Number]</planet_house>
	<influence>[Description of influence on personality]</influence>
	<traits>
	- [Trait 1]
	- [Trait 2]
	- [Trait 3]
	</traits>
	</interpretation>

	Very importantly, also explain the influence of the ascendant:
	<interpretation>
	<sign>Ascendant</sign>
	<influence>[Description of influence of ascendant on personality]</influence>
	<traits>
	- [Trait 1]
	- [Trait 2]
	- [Trait 3]
	</traits>
	</interpretation>

	Use appropriate astrological terminology and provide detailed explanations that demonstrate your
	expertise as an astrologer. Be sure to consider the unique qualities of each planet and how they
	interact with the energies of their respective houses.

	After interpreting all planet-house combinations, conclude with a brief overall summary of the
	person's astrological profile based on these placements. Present this summary in <summary> tags.

	Remember to maintain a professional and insightful tone throughout your interpretation, as befitting
	an expert astrologer.

	<formatting>
	Keep your answer to a maximum of 2048 tokens.
	Always answer in JSON format using the following structure:
	{{
		"mercury": {{
			"influence": string,
			"traits": list 
		}},
		"venus": {{
			"influence": string,
			"traits": list 
		}},
		"mars": {{
			"influence": string,
			"traits": list 
		}},
		"jupiter": {{
			"influence": string,
			"traits": list 
		}},
		"saturn": {{
			"influence": string,
			"traits": list 
		}},
		"uranus": {{
			"influence": string,
			"traits": list 
		}},
		"neptune": {{
			"influence": string,
			"traits": list 
		}},
		"pluto": {{
			"influence": string,
			"traits": list 
		}},
		"sun": {{
			"influence": string,
			"traits": list 
		}},
		"moon": {{
			"influence": string,
			"traits": list 
		}},
		"ascendant": {{
			"influence": string,
			"traits": list 
		}}
	}}
	</formatting>
	"""
	user = """
	Here is the list of planet-house combinations:

	<planet_houses>
	{PLANET_HOUSES}
	</planet_houses>

	Here is the ascendant sign information:
	<ascendant>
	{ASCENDANT}
	</ascendant>

	Please provide your analysis.
	"""
	return (system, user.format(
		PLANET_HOUSES=str(subject.planets),
		ASCENDANT=str(subject.ascendant)
	))

def parse_chart_response(response: str) -> ChartAnalysis:
	"""Parse the structured analysis response from Claude.
	
	Args:
		response: The raw response string from Claude API.
		
	Returns:
		ChartAnalysis: Parsed analysis content.

	Raises:
		ValueError: If the response format is invalid or parsing fails.
	"""
	interpolated_response = "{" + response
	try:
		json_data = json.loads(interpolated_response)
		return ChartAnalysis(**json_data)
	except json.JSONDecodeError as e:
		logger.error(f"Failed to parse personality analysis response: {e}")
		raise ValueError("Invalid response format") from e
	except Exception as e:
		logger.error(f"Unexpected error while parsing personality analysis response: {e}")
		raise ValueError("Error processing personality analysis response") from e

def build_personality_context(
	request: AnalysisRequest
) -> tuple[str, str]:
		
	birth_data = BirthData(
		birth_date=request.birth_date,
		birth_time=request.birth_time,
		latitude=request.latitude,
		longitude=request.longitude
	)
		 
	chart = generate_birth_chart(birth_data, with_svg=False)
		 
	system = """
	Your task is to analyze a birth chart and provide insights into the individual's personality, strengths, challenges, and life path. You
	will be given a birth chart with planetary positions and aspects. Use this information to create a
	comprehensive astrological analysis.

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

	Remember to use astrological terminology accurately but also explain concepts in a way that someone
	with basic astrological knowledge can understand. Provide a balanced view, highlighting both
	positive attributes and potential challenges. Avoid making absolute predictions; instead, focus on
	tendencies and potentials.

	<formatting>
	Keep your answer to a maximum of 2048 tokens.
	Always answer in JSON format using the following structure:
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

	user = """
	Here is the birth chart you will be analyzing:

	<birth_chart>
	{BIRTH_CHART}
	</birth_chart>
	"""
	return (system, user.format(BIRTH_CHART=chart.to_string()))

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

def build_horoscope_context(
	model: TransitsTimeRangeModel,
	charts: list[AstrologicalChart],
	horoscope_type: HoroscopePeriod
) -> tuple[str, str]:
	"""Build context for the horoscope request
	
	Args:
		model: TransitsTimeRangeModel containing transit data
		horoscope_type: Type of horoscope period (WEEK, MONTH, YEAR)
	
	Returns:
		Context string for Claude API with formatted transit data
	"""

	# Convert transits to a format suitable for Claude context
	transits = []
	for idx, moment in enumerate(model.transits):
		transit_data = {
			"date": str(moment.date) if moment.date else "Unknown",
			"aspects": [],
			"retrograding_planets": []
		}
		
		# Extract retrograding planets from the corresponding chart
		if idx < len(charts):
			chart = charts[idx]
			for planet_name, planet_data in chart.planets.items():
				if hasattr(planet_data, 'retrograde') and planet_data.retrograde:
					transit_data["retrograding_planets"].append(planet_name)

		# Format aspects in a readable way for Claude
		if hasattr(moment, 'aspects') and moment.aspects:
			for aspect in moment.aspects:
				aspect_info = {
					"aspect_name": getattr(aspect, 'aspect', 'Unknown'),
					"planet1": getattr(aspect, 'p1_name', 'Unknown'),
					"planet2": getattr(aspect, 'p2_name', 'Unknown'),
					"orb": getattr(aspect, 'orbit', 0),
					"aspect_degrees": getattr(aspect, 'aspect_degrees', 0)
				}
				transit_data["aspects"].append(aspect_info)
		
		transits.append(transit_data) 

	system: str = """
	You are an experienced astrology guru tasked with creating a horoscope based on a
	list of astrological aspects and a list of retrograding planets. Your goal is to interpret these aspects and provide insightful,
	engaging, and personalized astrological guidance.

	Your response should contain overall summary of the horoscope and specific
	findings for each date period mentioned in the aspects list.

	To create the horoscope:
	1. Carefully analyze each aspect provided, considering the planets involved, the nature of the
	aspect (conjunction, trine, square, etc.), and the zodiac signs if mentioned.
	2. Interpret how these aspects might influence various areas of life, such as relationships, career,
	personal growth, or finances, depending on the horoscope type requested.
	3. Consider the cumulative effect of multiple aspects occurring on the same day or in close
	succession.
	4. Tailor your interpretations to the specific horoscope type requested, ensuring relevance and
	coherence.

	When writing the horoscope:
	- Use language that is positive and empowering, even when discussing challenging aspects.
	- Balance specificity with generality to allow for personal interpretation by the reader.
	- Incorporate astrological terminology naturally, but ensure the content is accessible to those with
	limited astrological knowledge.
	- Maintain a tone that is wise, insightful, and slightly mystical, befitting an astrology guru.

	For the overall summary:
	- Provide a broad overview of the main themes and energies present in the entire period covered by
	the aspects.
	- Highlight any particularly significant or unusual astrological events.
	- Offer general advice or insights that apply to the whole period.

	For each specific date period:
	- Focus on the most prominent or impactful aspects for that time frame.
	- Describe how these aspects might manifest in the reader's life.
	- Provide practical suggestions or areas of focus based on the astrological influences.

	Remember to structure your final output as a JSON object with two main keys: "overall_summary" and
	"findings". The "findings" should be an array of objects, each containing a "date",
	a "horoscope" for that date, a list of the "active_aspects" on that date and a list of "retrograding_planets" on that date.

	<formatting>
	Keep your answer to a maximum of 2048 tokens.
	Always answer in JSON format using the following structure:
	{{
		"overvall_summary": string,
		"specific_findings": [
			"date": string,
			"horoscope": string,
			"active_aspects": list[string],
			"retrograding_planets": list[string]
		]
	}}
	</formatting>
	"""

	user: str = """
	Here is the list of astrological aspects you will be working with:
	<aspects>
	{ASTROLOGICAL_ASPECTS}
	</aspects>
	Please create a {HOROSCOPE_TYPE} horoscope.
	"""

	return (system, user.format(HOROSCOPE_TYPE=horoscope_type, ASTROLOGICAL_ASPECTS=transits))

def build_relationship_context(
	chart_1: AstrologicalChart,
	chart_2: AstrologicalChart,
	score: RelationshipScoreModel,
	relationship_type: str
) -> tuple[str, str]:
	"""Build context for relationship analysis request.
	
	Args:
		request: RelationshipAnalysisRequest containing birth data for both individuals.
		
	Returns:
		Tuple of (context, birth_chart_str) where:
		- context: Context string for Claude API
		- birth_chart_str: String representation of the birth chart
	"""

	if relationship_type not in ["romantic", "friendship", "professional"]:
		raise ValueError("Invalid relationship type. Must be one of: romantic, friendship, professional.")
	
	
	# Extract comprehensive information
	result = {
		"total_score": score.score_value,
		"is_destiny_sign": score.is_destiny_sign,
		"compatibility_level": score.score_description,
		"relationship_score_aspects": score.aspects
	}
	
	# Format aspects as meaningful strings
	formatted_aspects = []
	for aspect in score.aspects:
		if isinstance(aspect, dict):
			# Create a meaningful string representation: "Sun square Moon (4 points)"
			aspect_str = f"{aspect['p1_name']} {aspect['aspect']} {aspect['p2_name']} ({aspect['points']} points)"
			formatted_aspects.append(aspect_str)
		else:
			# Fallback for non-dict aspects
			formatted_aspects.append(str(aspect))
	
	# Update the result with formatted aspects
	result["formatted_aspects"] = formatted_aspects

	system = """
	You are an AI assistant trained in astrology and astronomy. Your task is to analyze the relationship compatibility between two individuals based on their birth charts. 
	This relationship type can be romantic, friendship or professional. You will be provided with the relationship type.
	You will also be provided with a relationship score, information about destiny signs, a list of astrological aspects contributing to the score and each person's birth chart information.
	Use this information to create a comprehensive astrological analysis of their relationship compatibility.

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
	Keep your answer to a maximum of 2048 tokens.
	Always answer in JSON format using the following structure:
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

	user = """
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
	"""
	return (system, user.format(
		RELATIONSHIP_TYPE=relationship_type,
		SCORE=result['total_score'],
		COMPATIBILITY_LEVEL=result['compatibility_level'],
		IS_DESTINY_SIGN="Yes" if result['is_destiny_sign'] else "No",
		SCORE_ASPECTS=", ".join(result['formatted_aspects']),
		BIRTH_CHART_A=chart_1.to_string(),
		BIRTH_CHART_B=chart_2.to_string()
	))

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

def build_chat_context(profile_data: Dict[str, str]) -> tuple[str, str]:
	"""Build the system context for Claude chat.
	
	Args:
			profile_data: Context information to be used by chat agent
			
	Returns:
			Complete context string for Claude
	"""

	system = """
	You are a knowledgeable and friendly astrologer. Your role is to provide insightful and personalized
	astrological guidance to users based on their birth chart, recent horoscope, personality analysis,
	and relationship analysis. Always maintain a warm, supportive, and mystical demeanor in your
	responses.

	When responding to user queries, follow these guidelines:

	1. Only mention the astrological information when it is directly relevant to the user's question or
	adds significant value to your response.
	2. Use the information to provide more personalized and accurate answers, but don't overwhelm the
	user with too much detail at once.
	3. If the user asks about a specific aspect of their chart or horoscope, focus on that area while
	briefly touching on related influences if appropriate.
	4. When discussing personality traits or relationship dynamics, refer to the personality analysis
	and relationship scores to enhance your insights.
	5. Always maintain a positive and encouraging tone, even when discussing challenging aspects or
	potential difficulties.

	To respond to a user query, follow these steps:

	1. Carefully read the user's question.
	2. Identify which pieces of astrological information (birth chart, horoscope, personality analysis,
	or relationship scores) are most relevant to the query.
	3. Formulate a response that addresses the user's question while incorporating relevant astrological
	insights.
	4. If appropriate, offer gentle advice or suggestions based on the astrological information.
	5. Conclude with an encouraging or thought-provoking statement related to the user's query and
	astrological profile.

	Present your response in the following format:

	<astro_response>
	[Your detailed response here, incorporating relevant astrological insights and addressing the user's
	query]
	</astro_response>

	Remember to always stay in character as a friendly and knowledgeable astrologer. Use the
	astrological information judiciously to provide meaningful and personalized guidance without
	overwhelming the user with technical details.
	"""
	user = """
	Here is the information about the user:

	<birth_chart>
	{BIRTH_CHART}
	</birth_chart>

	<horoscope>
	{HOROSCOPE}
	</horoscope>

	<personality_analysis>
	{PERSONALITY_ANALYSIS}
	</personality_analysis>

	<relationships>
	{RELATIONSHIPS}
	</relationships>

	Now respond to the user's query as instructed:
	"""
	return (system, user.format(
		BIRTH_CHART=profile_data[""],
		HOROSCOPE="",
		PERSONALITY_ANALYSIS="",
		RELATIONSHIPS=""
	))

def build_composite_context(
	composite_chart: AstrologicalChart
) -> tuple[str, str]:
	"""Build context for composite chart analysis request.
	
	Args:
		composite_chart: AstrologicalChart object containing the composite chart data.
		
	Returns:
		Context string for Claude API with composite chart analysis.
	"""
	
	system = """
	You are an expert astrologer specializing in composite chart analysis. Your task is to analyze a composite chart created from the midpoint method between two individuals' birth charts.

	A composite chart represents the essence of the relationship itself - not the individuals, but the dynamic energy that emerges when they come together. Use this composite chart to provide insights into the relationship's core themes, purpose, and potential.

	Analyze the composite chart carefully, paying attention to the following elements:
	1. Composite Sun sign and house position - the core identity and purpose of the relationship
	2. Composite Moon sign and house position - the emotional needs and domestic life of the relationship
	3. Composite Ascendant - how the relationship presents itself to the world
	4. Positions of other planets and their meanings for the relationship dynamic
	5. Important house emphases that show key relationship themes
	6. The overall energy and character of this union

	Based on your analysis, provide insights into:
	1. The relationship's core purpose and identity
	2. Emotional dynamics and domestic harmony
	3. Communication patterns within the relationship
	4. How the relationship expresses love and affection
	5. Potential challenges and growth areas
	6. The relationship's public image and social presence
	7. Long-term potential and evolution

	Remember that composite charts reveal the relationship's own personality - distinct from either individual's chart.

	Structure your response as follows:

	<formatting>
	Output your analysis in pure JSON structure:
	{{
		"overview": string,
		"relationship_identity": {{
			"description": string,
			"key_themes": list,
		}},
		"emotional_dynamics": {{
			"description": string,
			"emotional_patterns": list,
		}},
		"communication_style": {{
			"description": string,
			"communication_strengths": list,
		}},
		"love_expression": {{
			"description": string,
			"love_dynamics": list,
		}},
		"public_image": {{
			"description": string,
			"social_presence": list,
		}},
		"strengths_and_challenges": {{
			"strengths": list,
			"challenges": list,
		}},
		"long_term_potential": {{
			"overview": string,
			"growth_areas": list,
		}}
	}}
	</formatting>
	"""
	user = """
	Here is the composite chart you will be analyzing:

	<composite_chart>
	{COMPOSITE_CHART}
	</composite_chart>
	"""
	
	return (system, user.format(COMPOSITE_CHART=composite_chart.to_string()))

def parse_composite_response(response: str) -> CompositeAnalysis:
	"""Parse the structured composite analysis response from Claude.
	
	Args:
		response: The raw response string from Claude API.
		
	Returns:
		CompositeAnalysis: Parsed analysis content.
		
	Raises:
		ValueError: If the response format is invalid or parsing fails.
	"""
	interpolated_response = "{" + response
	try:
		json_data = json.loads(interpolated_response)
		return CompositeAnalysis(**json_data)
	except json.JSONDecodeError as e:
		logger.error(f"Failed to parse composite analysis response: {e}")
		raise ValueError("Invalid response format") from e
	except Exception as e:
		logger.error(f"Unexpected error while parsing composite analysis response: {e}")
		raise ValueError("Error processing composite analysis response") from e

def build_daily_horoscope_context(
	birth_data: BirthData,
	transit_data: DailyTransit
) -> tuple[str, str]:
	"""Build context for daily horoscope analysis based on transit data.
	
	Args:
		birth_data: Birth information of the user
		transit_data: Transit information for the specific date
		
	Returns:
		Tuple of (system_prompt, user_prompt) for Claude API
	"""
	
	system = """
	You are an expert astrologer tasked with creating a personalized daily horoscope based on transit data.
	You will receive birth information and specific transit aspects for a particular date.
	
	Your task is to interpret the transit aspects and create an engaging, insightful daily horoscope that:
	1. Focuses on how the transiting planets interact with the person's natal chart
	2. Provides practical guidance for the day
	3. Identifies key themes and energy levels
	4. Highlights specific focus areas for the individual
	
	Consider the following in your analysis:
	- The nature of each transit aspect (conjunction, square, trine, etc.)
	- The planets involved and their traditional meanings
	- Any retrograde planets and their influence
	- The cumulative effect of multiple transits
	- Practical applications for daily life
	
	Structure your response as follows:
	
	<formatting>
	Output your analysis in pure JSON structure:
	{{
		"horoscope_text": string,
		"key_themes": list[string],
		"energy_level": string, // "low", "moderate", "high", "intense"
		"focus_areas": list[string]
	}}
	</formatting>
	"""
	
	user = """
	Here is the birth information and transit data for the horoscope:
	
	<birth_data>
	Birth Date: {BIRTH_DATE}
	Birth Time: {BIRTH_TIME}
	Location: {LATITUDE}, {LONGITUDE}
	</birth_data>
	
	<transit_data>
	Date: {TARGET_DATE}
	Active Aspects: {ACTIVE_ASPECTS}
	Retrograde Planets: {RETROGRADE_PLANETS}
	Major Transits: {MAJOR_TRANSITS}
	</transit_data>
	
	Please create a personalized daily horoscope based on this information.
	"""
	
	return (system, user.format(
		BIRTH_DATE=birth_data.birth_date,
		BIRTH_TIME=birth_data.birth_time,
		LATITUDE=birth_data.latitude,
		LONGITUDE=birth_data.longitude,
		TARGET_DATE=transit_data.date,
	))