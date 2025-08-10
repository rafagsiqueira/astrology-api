from typing import Any, Dict, Optional

from astrology import generate_birth_chart
from models import AnalysisRequest, CosmiclogicalChart, BirthData, ChartAnalysis, DailyTransit, DailyTransitChange, HoroscopePeriod, PersonalityAnalysis, RelationshipAnalysis, CompositeAnalysis
from config import get_logger
from kerykeion.kr_types.kr_models import RelationshipScoreModel, TransitsTimeRangeModel   
import json

logger = get_logger(__name__)

def build_birth_chart_context(
	subject: CosmiclogicalChart
) -> tuple[str, str]:
	
	system: str = """
	You are an expert cosmicloger tasked with interpreting a person's cosmiclogical chart based on the
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

	Use appropriate cosmiclogical terminology and provide detailed explanations that demonstrate your
	expertise as an cosmicloger. Be sure to consider the unique qualities of each planet and how they
	interact with the energies of their respective houses.

	After interpreting all planet-house combinations, conclude with a brief overall summary of the
	person's cosmiclogical profile based on these placements. Present this summary in <summary> tags.

	Remember to maintain a professional and insightful tone throughout your interpretation, as befitting
	an expert cosmicloger.

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
	comprehensive cosmiclogical analysis.

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

	Remember to use cosmiclogical terminology accurately but also explain concepts in a way that someone
	with basic cosmiclogical knowledge can understand. Provide a balanced view, highlighting both
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

def build_relationship_context(
	chart_1: CosmiclogicalChart,
	chart_2: CosmiclogicalChart,
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
	You are an AI assistant trained in astrology and cosmicnomy. Your task is to analyze the relationship compatibility between two individuals based on their birth charts. 
	This relationship type can be romantic, friendship or professional. You will be provided with the relationship type.
	You will also be provided with a relationship score, information about destiny signs, a list of cosmiclogical aspects contributing to the score and each person's birth chart information.
	Use this information to create a comprehensive cosmiclogical analysis of their relationship compatibility.

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
	Discuss the key cosmiclogical aspects contributing to the relationship score.
	</relationship_aspects>
	<strengths>
	Identify the strengths of the relationship based on the analysis.
	</strengths>
	<challenges>
	Identify the challenges or potential areas of conflict in the relationship.
	</challenges>
	<areas_for_growth>
	Potential areas for growth for the couple based on the cosmiclogical analysis.
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
	You are a knowledgeable and friendly cosmicloger. Most of all you are a friendly shoulder to talk to.
	You may provide insightful and personalized cosmiclogical guidance to users based on their birth chart, recent horoscope, personality analysis,
	and relationship analysis. 
	
	Always maintain a warm, supportive, and mystical demeanor in your
	responses.

	When responding to user queries, follow these guidelines:

	1. Only mention the cosmiclogical information when it is directly relevant to the user's question or
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
	2. Identify if any cosmiclogical information (birth chart, horoscope, personality analysis,
	or relationship scores) is relevant to the query.
	3. Formulate a response that addresses the user's question, only incorporate relevant cosmiclogical
	insights, when applicable to the question. A simple hello, should be answered by a similar response. 
	You are not expected to overanalyze simple interactions.
	4. If appropriate, offer gentle advice or suggestions based on the cosmiclogical information.
	5. Conclude with an encouraging or thought-provoking statement related to the user's query and
	cosmiclogical profile.

	Present your response in the following format:

	[Your detailed response here, incorporating relevant cosmiclogical insights and addressing the user's
	query]

	Remember to always stay in character as a friendly and knowledgeable cosmicloger. Use the
	cosmiclogical information judiciously to provide meaningful and personalized guidance without
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
		BIRTH_CHART=profile_data.get("cosmiclogical_chart", "No birth chart data available."),
		HOROSCOPE=horoscopes_to_string(profile_data.get("horoscopes")),
		PERSONALITY_ANALYSIS=personality_analysis_to_string(profile_data.get("personality_analysis")),
		RELATIONSHIPS=relationships_to_string(profile_data.get("relationships"))
	))

def build_composite_context(
	composite_chart: CosmiclogicalChart
) -> tuple[str, str]:
	"""Build context for composite chart analysis request.
	
	Args:
		composite_chart: CosmiclogicalChart object containing the composite chart data.
		
	Returns:
		Context string for Claude API with composite chart analysis.
	"""
	
	system = """
	You are an expert cosmicloger specializing in composite chart analysis. Your task is to analyze a composite chart created from the midpoint method between two individuals' birth charts.

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

def build_horoscope_context(
	birth_chart: CosmiclogicalChart,
	transit_changes: DailyTransitChange
) -> tuple[str, str]:
	"""Build context for daily horoscope analysis based on transit data.
	
	Args:
		transit_changes: Transit changes information for the specific date
		
	Returns:
		Tuple of (system_prompt, user_prompt) for Claude API
	"""
	
	system = """
	You are an expert cosmicloger tasked with creating a personalized daily horoscope based on changing
	aspects and changes in retrograding planets. You will receive the user's birth chart and information about recent cosmiclogical
	changes relevant to the birth chart. Your goal is to interpret this information and
	create a meaningful, personalized horoscope for the user.

	Interpret the data you will receive and create a horoscope:

	1. Analyze the aspect changes:
	- Focus on aspects that have started or ended recently (within the last few days).
	- Consider the nature of the planets involved (p_1 is always a planet in the user's natal chart).
	- Interpret the type of aspect (conjunction, opposition, trine, etc.) and its potential influence.

	2. Evaluate the retrograde changes:
	-Pay attention to planets that have recently started or ended their retrograde motion.
	- Consider how these changes might affect the areas of life governed by these planets.

	3. Synthesize the information:
	- Look for patterns or themes in the recent changes.
	- Consider how these cosmiclogical shifts might manifest in the user's daily life.

	4. Create the horoscope:
	- Write a paragraph (3-5 sentences) that captures the overall energy or theme for the day.
	- Focus on 2-3 specific areas of life that are likely to be influenced by the recent changes.
	- Offer gentle advice or suggestions based on the cosmiclogical influences.
	- Keep the tone positive and empowering, even when discussing challenges.
	- Use language that is accessible to a general audience, avoiding overly technical cosmiclogical
	terms.

	5. Personalization:
	- Remember that this horoscope is personalized based on the user's birth chart, so make it feel
	tailored and specific.
	- Use phrases like "You may find that..." or "This is a good time for you to..." to emphasize the
	personal nature of the reading.

	6. Closing:
	- End with an encouraging statement or a positive affirmation related to the day's cosmiclogical
	influences.

	<formatting>
	Output your analysis in pure text. Aim for a total length of 150-200 words.
	</formatting>
	"""
	
	user = """
	Here is the birth chart:
	<birth_chart>
	{BIRTH_CHART}
	</birth_chart>

	Here is the list of relevant aspect changes:
	<aspect_changes>
	{ASPECT_CHANGES}
	</aspect_changes>

	Here is the list of changes in retrograding planets:
	<retrograde_changes>
	{RETROGRADE_CHANGES}
	</retrograde_changes>
	"""
	
	# Format aspect changes as human-readable strings
	aspect_changes = []
	for aspect in transit_changes.aspects.began:
		aspect_changes.append(f"{aspect.p1_name} {aspect.aspect} {aspect.p2_name} started")
	for aspect in transit_changes.aspects.ended:
		aspect_changes.append(f"{aspect.p1_name} {aspect.aspect} {aspect.p2_name} ended")
	
	# Format retrograde changes as human-readable strings
	retrograde_changes = []
	for planet in transit_changes.retrogrades.began:
		retrograde_changes.append(f"{planet} started retrograde")
	for planet in transit_changes.retrogrades.ended:
		retrograde_changes.append(f"{planet} ended retrograde")
	
	return (system, user.format(
		BIRTH_CHART=birth_chart.to_string(),
		ASPECT_CHANGES=aspect_changes,
		RETROGRADE_CHANGES=retrograde_changes
	))


def personality_analysis_to_string(personality_data: Optional[Any]) -> str:
	"""Convert personality analysis data to a readable string format.
	
	Args:
		personality_data: Dictionary containing personality analysis data or other data type
		
	Returns:
		Formatted string representation of personality analysis
	"""
	if not personality_data or not isinstance(personality_data, dict):
		return "No personality analysis available."
	
	sections = []
	
	# Overview
	if 'overview' in personality_data and personality_data['overview']:
		sections.append(f"Overview: {personality_data['overview']}")
	
	# Personality Traits
	if 'personality_traits' in personality_data and personality_data['personality_traits']:
		traits = personality_data['personality_traits']
		if isinstance(traits, list) and traits:
			sections.append(f"Personality Traits: {', '.join(str(t) for t in traits if t)}")
		elif isinstance(traits, str) and traits.strip():
			sections.append(f"Personality Traits: {traits}")
	
	# Emotional Nature
	if 'emotional_nature' in personality_data and personality_data['emotional_nature']:
		sections.append(f"Emotional Nature: {personality_data['emotional_nature']}")
	
	# Communication & Intellect
	if 'communication_intellect' in personality_data and personality_data['communication_intellect']:
		sections.append(f"Communication Style: {personality_data['communication_intellect']}")
	
	# Strengths
	if 'strengths' in personality_data and personality_data['strengths']:
		strengths = personality_data['strengths']
		if isinstance(strengths, list) and strengths:
			sections.append(f"Key Strengths: {', '.join(str(s) for s in strengths if s)}")
		elif isinstance(strengths, str) and strengths.strip():
			sections.append(f"Key Strengths: {strengths}")
	
	# Challenges
	if 'challenges' in personality_data and personality_data['challenges']:
		challenges = personality_data['challenges']
		if isinstance(challenges, list) and challenges:
			sections.append(f"Growth Areas: {', '.join(str(c) for c in challenges if c)}")
		elif isinstance(challenges, str) and challenges.strip():
			sections.append(f"Growth Areas: {challenges}")
	
	# Relationships
	if 'relationships' in personality_data and personality_data['relationships']:
		sections.append(f"Relationship Approach: {personality_data['relationships']}")
	
	# Career
	if 'career' in personality_data and personality_data['career']:
		sections.append(f"Career Guidance: {personality_data['career']}")
	
	# Life Path
	if 'life_path' in personality_data and personality_data['life_path']:
		sections.append(f"Life Path: {personality_data['life_path']}")
	
	# If no sections were found, return default message
	if not sections:
		return "No personality analysis available."
	
	return "\n\n".join(sections)


def relationships_to_string(relationships_data: Optional[Any]) -> str:
	"""Convert relationships data to a readable string format.
	
	Args:
		relationships_data: List of relationship dictionaries or other data type
		
	Returns:
		Formatted string representation of relationships
	"""
	if not relationships_data or not isinstance(relationships_data, list) or not relationships_data:
		return "No relationship analyses available."
	
	relationship_summaries = []
	
	for rel in relationships_data:
		if not isinstance(rel, dict):
			continue
			
		summary_parts = []
		
		# Relationship type and partner info
		rel_type = rel.get('relationship_type', '')
		partner_1_name = rel.get('partner_1_name', '')
		partner_2_name = rel.get('partner_2_name', '')
		
		# Only add if we have meaningful data
		if rel_type:
			summary_parts.append(f"Relationship Type: {rel_type}")
		if partner_1_name and partner_2_name:
			summary_parts.append(f"Partners: {partner_1_name} & {partner_2_name}")
		elif partner_1_name or partner_2_name:
			partner_name = partner_1_name or partner_2_name
			summary_parts.append(f"Partner: {partner_name}")
		
		# Analysis data
		if 'relationship_analysis' in rel and rel['relationship_analysis']:
			analysis = rel['relationship_analysis']
			if isinstance(analysis, dict):
				# Overall compatibility
				if 'overall_compatibility' in analysis and analysis['overall_compatibility']:
					summary_parts.append(f"Overall Compatibility: {analysis['overall_compatibility']}")
				
				# Compatibility score
				if 'compatibility_score' in analysis and analysis['compatibility_score'] is not None:
					score = analysis['compatibility_score']
					summary_parts.append(f"Compatibility Score: {score}/100")
				
				# Key strengths
				if 'strengths' in analysis and analysis['strengths']:
					strengths = analysis['strengths']
					if isinstance(strengths, list) and strengths:
						strength_list = [str(s) for s in strengths if s]
						if strength_list:
							summary_parts.append(f"Relationship Strengths: {', '.join(strength_list)}")
					elif isinstance(strengths, str) and strengths.strip():
						summary_parts.append(f"Relationship Strengths: {strengths}")
				
				# Challenges
				if 'challenges' in analysis and analysis['challenges']:
					challenges = analysis['challenges']
					if isinstance(challenges, list) and challenges:
						challenge_list = [str(c) for c in challenges if c]
						if challenge_list:
							summary_parts.append(f"Growth Areas: {', '.join(challenge_list)}")
					elif isinstance(challenges, str) and challenges.strip():
						summary_parts.append(f"Growth Areas: {challenges}")
				
				# Advice
				if 'advice' in analysis and analysis['advice']:
					summary_parts.append(f"Guidance: {analysis['advice']}")
		
		# Only add this relationship if we have some meaningful content
		if summary_parts:
			relationship_summaries.append("\n".join(summary_parts))
	
	# If no valid relationships found, return default message
	if not relationship_summaries:
		return "No relationship analyses available."
	
	return "\n\n---\n\n".join(relationship_summaries)


def horoscopes_to_string(horoscopes_data: Optional[Any]) -> str:
	"""Convert horoscope data to a readable string format.
	
	Args:
		horoscopes_data: Dictionary containing horoscope data or other data type
		
	Returns:
		Formatted string representation of horoscopes
	"""
	if not horoscopes_data or not isinstance(horoscopes_data, dict):
		return "No recent horoscope data available."
	
	sections = []
	
	# Check for different horoscope periods
	periods = ['daily', 'weekly', 'monthly', 'yearly']
	
	for period in periods:
		if period in horoscopes_data and horoscopes_data[period]:
			period_data = horoscopes_data[period]
			if isinstance(period_data, dict):
				# Extract the horoscope content
				content = period_data.get('content', '') or period_data.get('horoscope', '')
				date = period_data.get('date', '')
				
				if content and content.strip():
					section_title = f"{period.title()} Horoscope"
					if date:
						section_title += f" ({date})"
					sections.append(f"{section_title}:\n{content.strip()}")
			elif isinstance(period_data, str) and period_data.strip():
				sections.append(f"{period.title()} Horoscope:\n{period_data.strip()}")
	
	# If no structured periods found, look for general horoscope content
	if not sections:
		if isinstance(horoscopes_data, dict):
			content = horoscopes_data.get('content', '') or horoscopes_data.get('horoscope', '')
			if content and content.strip():
				sections.append(f"Horoscope:\n{content.strip()}")
		elif isinstance(horoscopes_data, str) and horoscopes_data.strip():
			sections.append(f"Horoscope:\n{horoscopes_data.strip()}")
	
	# If still no sections found, return default message
	if not sections:
		return "No recent horoscope data available."
	
	return "\n\n".join(sections)