"""
OrdinalMK — Platform Content Adapter
Generates platform-specific content from a single topic.
NO cross-posting. Each platform gets unique, adapted content.

Rules (2026):
- Instagram: Original captions, no identical cross-posts
- Twitter/X: Threads, short tweets, auto-post of own content ALLOWED
- LinkedIn: Professional tone, no automation of engagement
- TikTok: Completion rate > views, original audio preferred
- Facebook: Community-focused, shareable content
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

# --------------------------------------------------
# PLATFORM SPECS
# --------------------------------------------------
PLATFORM_SPECS = {
    'instagram': {
        'name': 'Instagram',
        'content_types': ['reel', 'carousel', 'story', 'post'],
        'max_caption': 2200,
        'max_hashtags': 30,
        'optimal_hashtags': 15,
        'image_ratio': '1:1 or 4:5',
        'best_times': {
            'es': ['07:00', '12:00', '19:00'],
            'en': ['08:00', '13:00', '20:00'],
            'pt': ['07:00', '12:00', '19:00'],
            'fr': ['08:00', '13:00', '20:00'],
            'de': ['08:00', '13:00', '19:00']
        },
        'tone': 'visual, inspiring, actionable',
        'format': 'caption + hashtags + CTA'
    },
    'twitter': {
        'name': 'Twitter/X',
        'content_types': ['tweet', 'thread', 'poll'],
        'max_tweet': 280,
        'max_thread': 25,
        'best_times': {
            'es': ['08:00', '12:00', '18:00'],
            'en': ['09:00', '12:00', '17:00'],
            'pt': ['08:00', '12:00', '18:00'],
            'fr': ['09:00', '12:00', '18:00'],
            'de': ['09:00', '12:00', '17:00']
        },
        'tone': 'concise, punchy, conversational',
        'format': 'short text + link or thread'
    },
    'linkedin': {
        'name': 'LinkedIn',
        'content_types': ['post', 'article', 'newsletter'],
        'max_post': 3000,
        'best_times': {
            'es': ['08:00', '12:00', '17:00'],
            'en': ['08:00', '12:00', '17:00'],
            'pt': ['08:00', '12:00', '17:00'],
            'fr': ['08:00', '12:00', '17:00'],
            'de': ['08:00', '12:00', '17:00']
        },
        'tone': 'professional, thought leadership, data-driven',
        'format': 'hook + story + insight + CTA'
    },
    'tiktok': {
        'name': 'TikTok',
        'content_types': ['video', 'photo_carousel'],
        'max_duration': 60,
        'optimal_duration': 15,
        'best_times': {
            'es': ['07:00', '12:00', '19:00'],
            'en': ['08:00', '12:00', '20:00'],
            'pt': ['07:00', '12:00', '19:00'],
            'fr': ['08:00', '12:00', '20:00'],
            'de': ['08:00', '12:00', '19:00']
        },
        'tone': 'authentic, fast-paced, hook in 3 seconds',
        'format': 'hook + value + CTA (15-60 sec video)'
    },
    'facebook': {
        'name': 'Facebook',
        'content_types': ['post', 'story', 'reel', 'group_post'],
        'max_caption': 63206,
        'best_times': {
            'es': ['09:00', '13:00', '20:00'],
            'en': ['09:00', '13:00', '20:00'],
            'pt': ['09:00', '13:00', '20:00'],
            'fr': ['09:00', '13:00', '20:00'],
            'de': ['09:00', '13:00', '20:00']
        },
        'tone': 'community, shareable, emotional',
        'format': 'story + value + question + CTA'
    }
}

# --------------------------------------------------
# HASHTAGS BY LANGUAGE AND TOPIC
# --------------------------------------------------
HASHTAGS = {
    'es': {
        'emprendimiento': ['#MujeresEmprendedoras', '#EmprendimientoFemenino', '#NegocioOnline', '#MujeresEnNegocios', '#Emprendedora', '#TriunfoFemenino', '#NegociosMujeres', '#YoEmprendo', '#MindsetEmprendedor', '#ÉxitoFemenino'],
        'productividad': ['#Productividad', '#OrganizaciónPersonal', '#GestiónDelTiempo', '#TipsDeProductividad', '#VidaOrganizada', '#PlanificadorDigital', '#RutinaProductiva', '#HábitosPositivos'],
        'salud': ['#SaludMenstrual', '#CicloMenstrual', '#BienestarFemenino', '#SaludDeLaMujer', '#Menstruación', '#Autocuidado', '#Bienestar'],
        'tecnologia': ['#MujeresEnTech', '#TecnologíaFemenina', '#DigitalTools', '#AppsParaMujeres', '#InnovaciónFemenina'],
        'general': ['#Yayika', '#Emprendimiento', '#MujerEmprendedora', '#NegocioDigital', '#Éxito']
    },
    'en': {
        'entrepreneurship': ['#WomenEntrepreneurs', '#FemaleFounders', '#WomenInBusiness', '#SideHustle', '#OnlineBusiness', '#WomenOwned', '#GirlBoss', '#Empowerment', '#StartupLife', '#WomenWhoLead'],
        'productivity': ['#Productivity', '#TimeManagement', '#DigitalPlanner', '#OrganizedLife', '#ProductiveHabits', '#GoalSetting', '#SelfImprovement'],
        'health': ['#WomensHealth', '#MenstrualHealth', '#CycleTracking', '#WellnessForWomen', '#SelfCare', '#HealthTips'],
        'technology': ['#WomenInTech', '#TechForWomen', '#DigitalTools', '#AppsForWomen', '#Innovation'],
        'general': ['#Yayika', '#Entrepreneurship', '#WomenEmpowerment', '#DigitalBusiness', '#Success']
    },
    'pt': {
        'empreendedorismo': ['#Empreendedoras', '#MulheresNegocios', '#NegócioOnline', '#EmpreendedorismoFeminino', '#MulherEmpreendedora', '#SucessoFeminino', '#NegóciosDigitais'],
        'produtividade': ['#Produtividade', '#OrganizaçãoPessoal', '#GestãoDeTempo', '#PlanejadorDigital', '#RotinaProdutiva'],
        'saude': ['#SaúdeDaMulher', '#CicloMenstrual', '#BemEstarFeminino', '#Autocuidado', '#Saúde'],
        'geral': ['#Yayika', '#Empreendedorismo', '#MulherEmpreendedora', '#NegócioDigital', '#Sucesso']
    },
    'fr': {
        'entrepreneuriat': ['#FemmesEntrepreneures', '#WomenInBusiness', '#EntrepreneuriatFéminin', '#BusinessEnLigne', '#FemmeEnAffaires', '#SuccèsFéminin'],
        'productivité': ['#Productivité', '#GestionDuTemps', '#PlanificateurDigital', '#Organisation', '#RoutineProductive'],
        'santé': ['#SantéFéminine', '#CycleMenstruel', '#BienÊtre', '#Autosoins', '#Santé'],
        'general': ['#Yayika', '#Entrepreneuriat', '#FemmeEntrepreneure', '#BusinessDigital', '#Succès']
    },
    'de': {
        'unternehmertum': ['#FrauenUnternehmerinnen', '#WomenInBusiness', '#Unternehmertum', '#OnlineBusiness', '#FrauenInBusiness', '#ErfolgWeiblich'],
        'produktivität': ['#Produktivität', '#Zeitmanagement', '#DigitalerPlaner', '#Organisation', '#ProduktiveGewohnheiten'],
        'gesundheit': ['#Frauengesundheit', '#ZyklusTracking', '#Wohlbefinden', '#Selbstfürsorge', '#Gesundheit'],
        'general': ['#Yayika', '#Unternehmertum', '#FrauenUnternehmerin', '#DigitalBusiness', '#Erfolg']
    }
}


class PlatformContentAdapter:
    """Generates platform-specific content from a single topic."""
    
    def __init__(self, project_id: str, languages: list):
        self.project_id = project_id
        self.languages = languages
    
    def adapt_content(self, topic: str, language: str, 
                      platforms: list = None) -> dict:
        """Adapt a single topic for multiple platforms."""
        if platforms is None:
            platforms = list(PLATFORM_SPECS.keys())
        
        results = {}
        
        for platform in platforms:
            if platform not in PLATFORM_SPECS:
                continue
            
            spec = PLATFORM_SPECS[platform]
            
            if platform == 'instagram':
                results[platform] = self._adapt_instagram(topic, language, spec)
            elif platform == 'twitter':
                results[platform] = self._adapt_twitter(topic, language, spec)
            elif platform == 'linkedin':
                results[platform] = self._adapt_linkedin(topic, language, spec)
            elif platform == 'tiktok':
                results[platform] = self._adapt_tiktok(topic, language, spec)
            elif platform == 'facebook':
                results[platform] = self._adapt_facebook(topic, language, spec)
        
        return {
            'topic': topic,
            'language': language,
            'platforms': results,
            'generated_at': datetime.now().isoformat()
        }
    
    def _adapt_instagram(self, topic: str, lang: str, spec: dict) -> dict:
        """Adapt content for Instagram (caption + hashtags)."""
        # Get hashtags for this language and topic category
        lang_hashtags = HASHTAGS.get(lang, HASHTAGS.get('es', {}))
        all_tags = []
        for category_tags in lang_hashtags.values():
            all_tags.extend(category_tags[:5])
        
        # Select optimal hashtags
        selected_tags = all_tags[:spec['optimal_hashtags']]
        hashtag_str = ' '.join(selected_tags)
        
        # Generate captions for different content types
        captions = {
            'reel': self._gen_reel_caption(topic, lang),
            'carousel': self._gen_carousel_caption(topic, lang),
            'story': self._gen_story_caption(topic, lang),
            'post': self._gen_post_caption(topic, lang)
        }
        
        return {
            'platform': 'Instagram',
            'content_types': captions,
            'hashtags': selected_tags,
            'hashtag_string': hashtag_str,
            'best_times': spec['best_times'].get(lang, spec['best_times']['en']),
            'image_ratio': spec['image_ratio'],
            'cta_options': self._gen_instagram_cta(lang)
        }
    
    def _adapt_twitter(self, topic: str, lang: str, spec: dict) -> dict:
        """Adapt content for Twitter/X (tweet + thread)."""
        # Short tweet
        tweet = self._gen_short_tweet(topic, lang)
        
        # Thread (5-7 tweets)
        thread = self._gen_thread(topic, lang)
        
        return {
            'platform': 'Twitter/X',
            'tweet': tweet,
            'thread': thread,
            'best_times': spec['best_times'].get(lang, spec['best_times']['en']),
            'cta_options': self._gen_twitter_cta(lang)
        }
    
    def _adapt_linkedin(self, topic: str, lang: str, spec: dict) -> dict:
        """Adapt content for LinkedIn (professional post)."""
        post = self._gen_linkedin_post(topic, lang)
        
        return {
            'platform': 'LinkedIn',
            'post': post,
            'best_times': spec['best_times'].get(lang, spec['best_times']['en']),
            'cta_options': self._gen_linkedin_cta(lang)
        }
    
    def _adapt_tiktok(self, topic: str, lang: str, spec: dict) -> dict:
        """Adapt content for TikTok (video script)."""
        script = self._gen_tiktok_script(topic, lang)
        
        return {
            'platform': 'TikTok',
            'script': script,
            'optimal_duration': f"{spec['optimal_duration']} seconds",
            'best_times': spec['best_times'].get(lang, spec['best_times']['en']),
            'hooks': self._gen_tiktok_hooks(topic, lang)
        }
    
    def _adapt_facebook(self, topic: str, lang: str, spec: dict) -> dict:
        """Adapt content for Facebook (community post)."""
        post = self._gen_facebook_post(topic, lang)
        
        return {
            'platform': 'Facebook',
            'post': post,
            'best_times': spec['best_times'].get(lang, spec['best_times']['en']),
            'cta_options': self._gen_facebook_cta(lang)
        }
    
    # --------------------------------------------------
    # CONTENT GENERATORS
    # --------------------------------------------------
    
    def _gen_reel_caption(self, topic: str, lang: str) -> str:
        """Generate Instagram Reel caption."""
        templates = {
            'es': f"POV: Descubres {topic.lower()} y todo cambia\n\n Este es el tip que necesitabas escuchar hoy\n Guarda este reel para después\n\n{topic} es el primer paso para transformar tu negocio\n\n #Reels #Tips #Emprendimiento",
            'en': f"POV: You discover {topic.lower()} and everything changes\n\n This is the tip you needed to hear today\n Save this reel for later\n\n{topic} is the first step to transform your business\n\n #Reels #Tips #Entrepreneurship",
            'pt': f"POV: Voce descobre {topic.lower()} e tudo muda\n\n Essa e a dica que voce precisava ouvir hoje\n Salve este reel para depois\n\n{topic} e o primeiro passo para transformar seu negocio\n\n #Reels #Dicas #Empreendedorismo",
            'fr': f"POV: Vous decouvrez {topic.lower()} et tout change\n\n C'est le conseil dont vous aviez besoin aujourd'hui\n Sauvegardez ce reel pour plus tard\n\n{topic} est la premiere etape pour transformer votre business\n\n #Reels #Conseils #Entrepreneuriat",
            'de': f"POV: Du entdeckst {topic.lower()} und alles andert sich\n\n Das ist der Tipp, den du heute horen musstest\n Speichere dieses Reel fur spater\n\n{topic} ist der erste Schritt, um dein Business zu transformieren\n\n #Reels #Tipps #Unternehmertum"
        }
        return templates.get(lang, templates['es'])
    
    def _gen_carousel_caption(self, topic: str, lang: str) -> str:
        """Generate Instagram Carousel caption."""
        templates = {
            'es': f"DESPLAZA PARA VER 5 pasos sobre {topic.lower()}:\n\n1️⃣ Paso uno\n2️⃣ Paso dos\n3️⃣ Paso tres\n4️⃣ Paso cuatro\n5️⃣ Paso cinco\n\n Guarda este post y comparte con quien lo necesite\n\n{topic} no tiene que ser complicado\n\n #Carousel #Educacion #Emprendimiento",
            'en': f"SWIPE TO SEE 5 steps about {topic.lower()}:\n\n1️⃣ Step one\n2️⃣ Step two\n3️⃣ Step three\n4️⃣ Step four\n5️⃣ Step five\n\n Save this post and share with someone who needs it\n\n{topic} doesn't have to be complicated\n\n #Carousel #Education #Entrepreneurship",
            'pt': f"DESLIZE PARA VER 5 passos sobre {topic.lower()}:\n\n1️⃣ Passo um\n2️⃣ Passo dois\n3️⃣ Passo tres\n4️⃣ Passo quatro\n5️⃣ Passo cinco\n\n Salve este post e compartilhe com quem precisa\n\n{topic} nao tem que ser complicado\n\n #Carousel #Educacao #Empreendedorismo",
            'fr': f"GLISSEZ POUR VOIR 5 etapes sur {topic.lower()}:\n\n1️⃣ Etape 1\n2️⃣ Etape 2\n3️⃣ Etape 3\n4️⃣ Etape 4\n5️⃣ Etape 5\n\n Sauvegardez ce post et partagez avec celui qui en a besoin\n\n{topic} n'a pas ete complique\n\n #Carousel #Education #Entrepreneuriat",
            'de': f"SCROLL FUR 5 Schritte zu {topic.lower()}:\n\n1️⃣ Schritt 1\n2️⃣ Schritt 2\n3️�️ Schritt 3\n4️�️ Schritt 4\n5️�️ Schritt 5\n\n Speichere diesen Post und teile ihn mit jemandem, der es braucht\n\n{topic} muss nicht kompliziert sein\n\n #Carousel #Bildung #Unternehmertum"
        }
        return templates.get(lang, templates['es'])
    
    def _gen_story_caption(self, topic: str, lang: str) -> str:
        """Generate Instagram Story text."""
        templates = {
            'es': f"¿Sabias que {topic.lower()} puede cambiar tu negocio?\n\n Descubre como en el link de la bio\n\n Swipe up",
            'en': f"Did you know {topic.lower()} can change your business?\n\n Find out how at the link in bio\n\n Swipe up",
            'pt': f"Voce sabia que {topic.lower()} pode mudar seu negocio?\n\n Descubra como no link da bio\n\n Deslize para cima",
            'fr': f"Le saviez-vous {topic.lower()} peut changer votre business?\n\n Decouvrez comment dans le lien en bio\n\n Glissez vers le haut",
            'de': f"Wusstest du, dass {topic.lower()} dein Business andern kann?\n\n Erfahre wie im Link in Bio\n\n Nach oben wischen"
        }
        return templates.get(lang, templates['es'])
    
    def _gen_post_caption(self, topic: str, lang: str) -> str:
        """Generate Instagram static post caption."""
        templates = {
            'es': f"{topic.title()} es una de las habilidades mas importantes que puedes desarrollar como emprendedora.\n\n En Yayika te ayudamos a dominar {topic.lower()} paso a paso.\n\n Comienza tu camino hoy\n\n Link en bio",
            'en': f"{topic.title()} is one of the most important skills you can develop as an entrepreneur.\n\n At Yayika we help you master {topic.lower()} step by step.\n\n Start your journey today\n\n Link in bio",
            'pt': f"{topic.title()} e uma das habilidades mais importantes que voce pode desenvolver como empreendedora.\n\n No Yayika te ajudamos a dominar {topic.lower()} passo a passo.\n\n Comece sua jornada hoje\n\n Link na bio",
            'fr': f"{topic.title()} est l'une des competences les plus importantes que vous puissiez developper en tant qu'entrepreneure.\n\n Chez Yayika, nous vous aidons a maitriser {topic.lower()} pas a pas.\n\n Commencez votre parcours aujourd'hui\n\n Lien en bio",
            'de': f"{topic.title()} ist eine der wichtigsten Fertigkeiten, die du als Unternehmerin entwickeln kannst.\n\n Bei Yayika helfen wir dir, {topic.lower()} Schritt fur Schritt zu meistern.\n\n Beginne deine Reise heute\n\n Link in Bio"
        }
        return templates.get(lang, templates['es'])
    
    def _gen_short_tweet(self, topic: str, lang: str) -> str:
        """Generate short tweet (under 280 chars)."""
        templates = {
            'es': f"{topic} es la habilidad que te falta para crecer tu negocio.\n\n Yo aprendi esto y todo cambio.\n\n Te comparto los 3 puntos clave en el hilo",
            'en': f"{topic} is the skill you're missing to grow your business.\n\n I learned this and everything changed.\n\n Here are the 3 key points in the thread",
            'pt': f"{topic} e a habilidade que falta para crescer seu negocio.\n\n Aprendi isso e tudo mudou.\n\n Compartilho os 3 pontos-chave no fio",
            'fr': f"{topic} est la competence qu'il vous manque pour developper votre business.\n\n J'ai appris ca et tout a change.\n\n Voici les 3 points cles dans le fil",
            'de': f"{topic} ist die Fertigkeit, die dir fehlt, um dein Business zu wachsen.\n\n Ich habe das gelernt und alles hat sich geandert.\n\n Hier sind die 3 Kernpunkte im Thread"
        }
        return templates.get(lang, templates['es'])
    
    def _gen_thread(self, topic: str, lang: str) -> list:
        """Generate Twitter thread (5-7 tweets)."""
        threads = {
            'es': [
                f"🧵 Hilo sobre {topic}\n\n Si quieres crecer tu negocio, esto es lo que necesitas saber:",
                f"1/ {topic} no es opcional.\n\n Es la base para escalar tu negocio de manera sostenible.",
                f"2/ El error mas comun es no tener un sistema.\n\n Sin sistema, cada dia es un caos.",
                f"3/ La solucion es simple: automatiza lo repetitivo.\n\n Dedica tu tiempo a lo que genera valor.",
                f"4/ En Yayika te damos las herramientas para hacerlo.\n\n Sin complicaciones, sin excusas.",
                f"5/ Resumen:\n\n ✅ Ten un sistema\n ✅ Automatiza lo repetitivo\n ✅ Enfocate en crear valor\n\n Guarda este hilo",
                f"6/ Si quieres aprender mas sobre {topic.lower()}, seguime para mas tips.\n\n Y visita yayika.com para comenzar"
            ],
            'en': [
                f"🧵 Thread about {topic}\n\n If you want to grow your business, here's what you need to know:",
                f"1/ {topic} is not optional.\n\n It's the foundation for scaling your business sustainably.",
                f"2/ The biggest mistake is not having a system.\n\n Without a system, every day is chaos.",
                f"3/ The solution is simple: automate the repetitive.\n\n Dedicate your time to what creates value.",
                f"4/ At Yayika we give you the tools to do it.\n\n No complications, no excuses.",
                f"5/ Summary:\n\n ✅ Have a system\n ✅ Automate repetitive tasks\n ✅ Focus on creating value\n\n Save this thread",
                f"6/ If you want to learn more about {topic.lower()}, follow me for more tips.\n\n And visit yayika.com to get started"
            ],
            'pt': [
                f"🧵 Fio sobre {topic}\n\n Se voce quer crescer seu negocio, aqui esta o que precisa saber:",
                f"1/ {topic} nao e opcional.\n\n E a base para escalar seu negocio de forma sustentavel.",
                f"2/ O erro mais comum e nao ter um sistema.\n\n Sem sistema, cada dia e um caos.",
                f"3/ A solucao e simples: automatize o repetitivo.\n\n Dedique seu tempo ao que gera valor.",
                f"4/ No Yayika te damos as ferramentas para fazer isso.\n\n Sem complicacoes, sem desculpas.",
                f"5/ Resumo:\n\n ✅ Tenha um sistema\n ✅ Automatize o repetitivo\n ✅ Foco em criar valor\n\n Salve este fio",
                f"6/ Se voce quer aprender mais sobre {topic.lower()}, me siga para mais dicas.\n\n E visite yayika.com para comecar"
            ],
            'fr': [
                f"🧵 Fil sur {topic}\n\n Si vous voulez developper votre business, voici ce qu'il faut savoir:",
                f"1/ {topic} n'est pas optionnel.\n\n C'est la base pour developper votre business de facon durable.",
                f"2/ L'erreur la plus courante est de ne pas avoir de systeme.\n\n Sans systeme, chaque jour est un chaos.",
                f"3/ La solution est simple: automatisez le repetitif.\n\n Dediquez votre temps a ce qui cree de la valeur.",
                f"4/ Chez Yayika, nous vous donnons les outils pour le faire.\n\n Sans complications, sans excuses.",
                f"5/ Resume:\n\n ✅ Ayez un systeme\n ✅ Automatisez le repetitif\n ✅ Concentrez-vous sur la creation de valeur\n\n Sauvegardez ce fil",
                f"6/ Si vous voulez en savoir plus sur {topic.lower()}, suivez-moi pour plus de conseils.\n\n Et visitez yayika.com pour commencer"
            ],
            'de': [
                f"🧵 Thread uber {topic}\n\n Wenn du dein Business wachsen lassen willst, hier ist, was du wissen musst:",
                f"1/ {topic} ist nicht optional.\n\n Es ist die Grundlage, um dein Business nachhaltig zu skalieren.",
                f"2/ Der haufigste Fehler ist, kein System zu haben.\n\n Ohne System ist jeder Tag Chaos.",
                f"3/ Die Losung ist einfach: Automatisiere Wiederholendes.\n\n Widme deine Zeit dem, was Wert schafft.",
                f"4/ Bei Yayika geben wir dir die Werkzeuge dafur.\n\n Keine Komplikationen, keine Ausreden.",
                f"5/ Zusammenfassung:\n\n ✅ Hab ein System\n ✅ Automatisiere Wiederholendes\n ✅ Konzentriere dich auf Wert创作\n\n Speichere diesen Thread",
                f"6/ Wenn du mehr uber {topic.lower()} lernen willst, folge mir fur mehr Tipps.\n\n Und besuche yayika.com um zu starten"
            ]
        }
        return threads.get(lang, threads['es'])
    
    def _gen_linkedin_post(self, topic: str, lang: str) -> str:
        """Generate LinkedIn post (professional)."""
        templates = {
            'es': f"¿Sabias que el 80% de las emprendedoras no tienen un sistema para {topic.lower()}?\n\n Despues de trabajar con cientos de mujeres, veo el mismo patron:\n\n → Muchas ideas, poco sistema\n → Mucho trabajo, pocos resultados\n → Mucho esfuerzo, poca escalabilidad\n\n La diferencia entre las que crecen y las que se estancan?\n\n UN SISTEMA.\n\n En Yayika construimos ese sistema para ti.\n\n Sin complicaciones. Sin excusas. Solo resultados.\n\n ¿Quieres saber mas? Comenta 'SISTEMA' y te comparto los detalles.\n\n #Emprendimiento #MujeresEmprendedoras #Negocios",
            'en': f"Did you know that 80% of women entrepreneurs don't have a system for {topic.lower()}?\n\n After working with hundreds of women, I see the same pattern:\n\n → Many ideas, little system\n → Much work, few results\n → Much effort, low scalability\n\n The difference between those who grow and those who stagnate?\n\n A SYSTEM.\n\n At Yayika we build that system for you.\n\n No complications. No excuses. Just results.\n\n Want to know more? Comment 'SYSTEM' and I'll share the details.\n\n #Entrepreneurship #WomenEntrepreneurs #Business",
            'pt': f"Voce sabia que 80% das empreendedoras nao tem um sistema para {topic.lower()}?\n\n Depois de trabalhar com centenas de mulheres, vejo o mesmo padrao:\n\n → Muitas ideias, pouco sistema\n → Muito trabalho, poucos resultados\n → Muito esforco, pouca escalabilidade\n\n A diferenca entre as que crescem e as que estagnam?\n\n UM SISTEMA.\n\n No Yayika construimos esse sistema para voce.\n\n Sem complicacoes. Sem desculpas. Apenas resultados.\n\n Quer saber mais? Comente 'SISTEMA' e compartilho os detalhes.\n\n #Empreendedorismo #MulheresNegocios #Negocios",
            'fr': f"Le saviez-vous que 80% des femmes entrepreneures n'ont pas de systeme pour {topic.lower()}?\n\n Apres avoir travaille avec des centaines de femmes, je vois le meme schema:\n\n → Beaucoup d'idees, peu de systeme\n → Beaucoup de travail, peu de resultats\n → Beaucoup d'efforts, faible scalabilite\n\n La difference entre celles qui grandissent et celles qui stagnent?\n\n UN SYSTEME.\n\n Chez Yayika, nous construisons ce systeme pour vous.\n\n Sans complications. Sans excuses. Juste des resultats.\n\n Vous voulez en savoir plus? Commentez 'SYSTEME' et je partage les details.\n\n #Entrepreneuriat #FemmesEntrepreneures #Business",
            'de': f"Wusstest du, dass 80% der Unternehmerinnen kein System fur {topic.lower()} haben?\n\n Nach der Arbeit mit Hunderten von Frauen sehe ich dasselbe Muster:\n\n → Viele Ideen, wenig System\n → Viel Arbeit, wenig Ergebnisse\n → Viel Aufwand, geringe Skalierbarkeit\n\n Der Unterschied zwischen denen, die wachsen, und denen, die stagnieren?\n\n EIN SYSTEM.\n\n Bei Yayika bauen wir dieses System fur dich.\n\n Keine Komplikationen. Keine Ausreden. Nur Ergebnisse.\n\n Willst du mehr wissen? Kommentiere 'SYSTEM' und ich teile die Details.\n\n #Unternehmertum #FrauenUnternehmerinnen #Business"
        }
        return templates.get(lang, templates['es'])
    
    def _gen_tiktok_script(self, topic: str, lang: str) -> dict:
        """Generate TikTok video script."""
        templates = {
            'es': {
                'hook': f"Si no tienes esto, tu negocio no va a crecer",
                'body': f"Muchas emprendedoras me preguntan como escalar {topic.lower()}. La respuesta es simple: necesitas un sistema. Sin sistema, cada dia es caos. Con sistema, cada dia es progreso.",
                'cta': f"Visita yayika.com para comenzar",
                'on_screen_text': [f"{topic}", "Sin sistema = caos", "Con sistema = progreso", "yayika.com"]
            },
            'en': {
                'hook': f"If you don't have this, your business won't grow",
                'body': f"Many women entrepreneurs ask me how to scale {topic.lower()}. The answer is simple: you need a system. Without a system, every day is chaos. With a system, every day is progress.",
                'cta': f"Visit yayika.com to get started",
                'on_screen_text': [f"{topic}", "No system = chaos", "With system = progress", "yayika.com"]
            },
            'pt': {
                'hook': f"Se voce nao tem isso, seu negocio nao vai crescer",
                'body': f"Muitas empreendedoras me perguntam como escalar {topic.lower()}. A resposta e simples: voce precisa de um sistema. Sem sistema, cada dia e caos. Com sistema, cada dia e progresso.",
                'cta': f"Visite yayika.com para comecar",
                'on_screen_text': [f"{topic}", "Sem sistema = caos", "Com sistema = progresso", "yayika.com"]
            },
            'fr': {
                'hook': f"Si vous n'avez pas ca, votre business ne grandira pas",
                'body': f"Beaucoup de femmes entrepreneures me demandent comment developper {topic.lower()}. La reponse est simple: vous avez besoin d'un systeme. Sans systeme, chaque jour est un chaos. Avec un systeme, chaque jour est un progres.",
                'cta': f"Visitez yayika.com pour commencer",
                'on_screen_text': [f"{topic}", "Sans systeme = chaos", "Avec systeme = progres", "yayika.com"]
            },
            'de': {
                'hook': f"Wenn du das nicht hast, wird dein Business nicht wachsen",
                'body': f"Viele Unternehmerinnen fragen mich, wie man {topic.lower()} skaliert. Die Antwort ist einfach: Du brauchst ein System. Ohn System ist jeder Tag Chaos. Mit System ist jeder Tag Fortschritt.",
                'cta': f"Besuche yayika.com um zu starten",
                'on_screen_text': [f"{topic}", "Kein System = Chaos", "Mit System = Fortschritt", "yayika.com"]
            }
        }
        return templates.get(lang, templates['es'])
    
    def _gen_tiktok_hooks(self, topic: str, lang: str) -> list:
        """Generate TikTok hooks (first 3 seconds)."""
        hooks = {
            'es': [
                f"Esto es lo que nadie te dice sobre {topic.lower()}",
                f"Si haces esto, tu negocio va a crecer",
                f"El error mas grande que cometen las emprendedoras",
                f"3 cosas que necesitas saber sobre {topic.lower()}",
                f"POV: Descubres el secreto de {topic.lower()}"
            ],
            'en': [
                f"This is what nobody tells you about {topic.lower()}",
                f"If you do this, your business will grow",
                f"The biggest mistake women entrepreneurs make",
                f"3 things you need to know about {topic.lower()}",
                f"POV: You discover the secret of {topic.lower()}"
            ],
            'pt': [
                f"Isso e o que ninguem te fala sobre {topic.lower()}",
                f"Se voce fizer isso, seu negocio vai crescer",
                f"O maior erro que empreendedoras cometem",
                f"3 coisas que voce precisa saber sobre {topic.lower()}",
                f"POV: Voce descobre o segredo de {topic.lower()}"
            ],
            'fr': [
                f"C'est ce que personne ne vous dit sur {topic.lower()}",
                f"Si vous faites ca, votre business va grandir",
                f"La plus grande erreur que font les femmes entrepreneures",
                f"3 choses que vous devez savoir sur {topic.lower()}",
                f"POV: Vous decouvrez le secret de {topic.lower()}"
            ],
            'de': [
                f"Das ist, was dir niemand uber {topic.lower()} sagt",
                f"Wenn du das machst, wird dein Business wachsen",
                f"Der grosste Fehler, den Unternehmerinnen machen",
                f"3 Dinge, die du uber {topic.lower()} wissen musst",
                f"POV: Du entdeckst das Geheimnis von {topic.lower()}"
            ]
        }
        return hooks.get(lang, hooks['es'])
    
    def _gen_facebook_post(self, topic: str, lang: str) -> str:
        """Generate Facebook post (community-focused)."""
        templates = {
            'es': f"Pregunta para la comunidad:\n\n ¿Como manejas {topic.lower()} en tu negocio?\n\n Yo empece con un sistema simple y todo cambio.\n\n Si quieres saber mas, visita yayika.com\n\n ¿Tu que estrategia usas? Cuenta en los comentarios",
            'en': f"Question for the community:\n\n How do you handle {topic.lower()} in your business?\n\n I started with a simple system and everything changed.\n\n If you want to know more, visit yayika.com\n\n What strategy do you use? Tell us in the comments",
            'pt': f"Pergunta para a comunidade:\n\n Como voce lida com {topic.lower()} no seu negocio?\n\n Comecei com um sistema simples e tudo mudou.\n\n Se voce quer saber mais, visite yayika.com\n\n Que estrategia voce usa? Conte nos comentarios",
            'fr': f"Question pour la communaute:\n\n Comment gererez-vous {topic.lower()} dans votre business?\n\n J'ai commence avec un systeme simple et tout a change.\n\n Si vous voulez en savoir plus, visitez yayika.com\n\n Quelle strategie utilisez-vous? Dites-nous en commentaire",
            'de': f"Fur die Community:\n\n Wie gehst du mit {topic.lower()} in deinem Business um?\n\n Ich habe mit einem einfachen System angefangen und alles hat sich geandert.\n\n Wenn du mehr wissen willst, besuche yayika.com\n\n Welche Strategie verwendest du? Schreib es in die Kommentare"
        }
        return templates.get(lang, templates['es'])
    
    # --------------------------------------------------
    # CTA GENERATORS
    # --------------------------------------------------
    
    def _gen_instagram_cta(self, lang: str) -> list:
        """Generate Instagram CTAs."""
        ctas = {
            'es': ['Link en bio', 'Guarda este post', 'Comparte con una amiga', 'Etiqueta a alguien que necesite esto', 'Desliza para ver mas'],
            'en': ['Link in bio', 'Save this post', 'Share with a friend', 'Tag someone who needs this', 'Swipe for more'],
            'pt': ['Link na bio', 'Salve este post', 'Compartilhe com uma amiga', 'Marque alguem que precise disso', 'Deslize para ver mais'],
            'fr': ['Lien en bio', 'Sauvegardez ce post', 'Partagez avec une amie', 'Mentionnez quelqu\'un qui en a besoin', 'Glissez pour plus'],
            'de': ['Link in Bio', 'Speichere diesen Post', 'Teile mit einer Freundin', 'Markiere jemanden, der es braucht', 'Scrolle fur mehr']
        }
        return ctas.get(lang, ctas['es'])
    
    def _gen_twitter_cta(self, lang: str) -> list:
        """Generate Twitter CTAs."""
        ctas = {
            'es': ['Guarda este tweet', 'Retuitea si te sirvio', 'Sigueme para mas tips', 'Hilo completo abajo'],
            'en': ['Save this tweet', 'Retweet if helpful', 'Follow for more tips', 'Full thread below'],
            'pt': ['Salve este tweet', 'Retuite se util', 'Siga para mais dicas', 'Fio completo abaixo'],
            'fr': ['Sauvegardez ce tweet', 'Retweetez si utile', 'Suivez-moi pour plus de conseils', 'Fil complet ci-dessous'],
            'de': ['Speichere diesen Tweet', 'Retweete, wenn hilfreich', 'Folge mir fur mehr Tipps', 'Vollstandiger Thread unten']
        }
        return ctas.get(lang, ctas['es'])
    
    def _gen_linkedin_cta(self, lang: str) -> list:
        """Generate LinkedIn CTAs."""
        ctas = {
            'es': ['Comenta tu experiencia', 'Guarda este post', 'Comparte con tu red', 'Visita yayika.com'],
            'en': ['Comment your experience', 'Save this post', 'Share with your network', 'Visit yayika.com'],
            'pt': ['Comente sua experiencia', 'Salve este post', 'Compartilhe com sua rede', 'Visite yayika.com'],
            'fr': ['Commentez votre experience', 'Sauvegardez ce post', 'Partagez avec votre reseau', 'Visitez yayika.com'],
            'de': ['Kommentiere deine Erfahrung', 'Speichere diesen Post', 'Teile mit deinem Netzwerk', 'Besuche yayika.com']
        }
        return ctas.get(lang, ctas['es'])
    
    def _gen_facebook_cta(self, lang: str) -> list:
        """Generate Facebook CTAs."""
        ctas = {
            'es': ['Responde en los comentarios', 'Comparte en tu muro', 'Unete al grupo', 'Visita yayika.com'],
            'en': ['Answer in comments', 'Share to your wall', 'Join the group', 'Visit yayika.com'],
            'pt': ['Responda nos comentarios', 'Compartilhe no seu muro', 'Junte-se ao grupo', 'Visite yayika.com'],
            'fr': ['Repondez en commentaire', 'Partagez sur votre mur', 'Rejoignez le groupe', 'Visitez yayika.com'],
            'de': ['Antworte in den Kommentaren', 'Teile auf deiner Pinnwand', 'Tritt der Gruppe bei', 'Besuche yayika.com']
        }
        return ctas.get(lang, ctas['es'])


class ContentCalendar:
    """Generate multi-platform content calendar."""
    
    def __init__(self, project_id: str, languages: list):
        self.project_id = project_id
        self.languages = languages
        self.adapter = PlatformContentAdapter(project_id, languages)
    
    def generate_calendar(self, topics: dict, days: int = 7) -> dict:
        """Generate content calendar for multiple platforms and languages."""
        calendar = {
            'project': self.project_id,
            'languages': self.languages,
            'days': [],
            'generated_at': datetime.now().isoformat()
        }
        
        platforms = ['instagram', 'twitter', 'linkedin', 'tiktok', 'facebook']
        
        for day_offset in range(days):
            date = (datetime.now() + timedelta(days=day_offset)).strftime('%Y-%m-%d')
            day_data = {
                'date': date,
                'content': {}
            }
            
            for lang in self.languages:
                lang_topics = topics.get(lang, topics.get(self.languages[0], []))
                if not lang_topics:
                    continue
                
                # Rotate topics
                topic_index = day_offset % len(lang_topics)
                topic = lang_topics[topic_index]
                
                # Adapt for all platforms
                adapted = self.adapter.adapt_content(topic, lang, platforms)
                day_data['content'][lang] = adapted
            
            calendar['days'].append(day_data)
        
        return calendar
    
    def save_calendar(self, calendar: dict) -> str:
        """Save calendar to file."""
        output_dir = Path(__file__).parent.parent.parent / "published" / self.project_id
        output_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = output_dir / "content_calendar.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(calendar, f, indent=2, ensure_ascii=False)
        
        return str(filepath)


if __name__ == "__main__":
    adapter = PlatformContentAdapter('yayika', ['es', 'en', 'pt', 'fr', 'de'])
    
    # Test adaptation
    result = adapter.adapt_content('Como emprender siendo mujer', 'es')
    
    print("Instagram:")
    print(f"  Reel: {result['platforms']['instagram']['content_types']['reel'][:100]}...")
    print(f"  Hashtags: {result['platforms']['instagram']['hashtag_string'][:100]}...")
    
    print("\nTwitter:")
    print(f"  Tweet: {result['platforms']['twitter']['tweet'][:100]}...")
    print(f"  Thread: {len(result['platforms']['twitter']['thread'])} tweets")
    
    print("\nLinkedIn:")
    print(f"  Post: {result['platforms']['linkedin']['post'][:100]}...")
    
    print("\nTikTok:")
    print(f"  Hook: {result['platforms']['tiktok']['script']['hook']}")
    print(f"  Duration: {result['platforms']['tiktok']['optimal_duration']}")
    
    print("\nFacebook:")
    print(f"  Post: {result['platforms']['facebook']['post'][:100]}...")
