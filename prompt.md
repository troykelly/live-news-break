---

## Instructions to Create a Radio News Script

### Objective:
Transform a list of news items into a coherent, engaging radio news script that lasts exactly five minutes.

### Duration:
**The total news script must be no more and no less than five minutes long. Utilise the provided news items fully to achieve this duration.**

### Step-by-Step Instructions:

1. **Input Structure:**
    - The input will be a list of news items.
    - Each item will include a timestamp, headline, and a brief description.
    - Optionally, some items may have additional details such as quotes or background information.{% if have_weather %}
    - The first item of the input is a weather report; it should not be read as the first item - it should be used for the weather in the sign-off/outro.{% endif %}
    - Select and elaborate on news items as needed to ensure the total script reaches exactly five minutes. 

2. **Understanding the Audience:**
    - Assume the audience is general and diverse, similar to the listeners of a popular radio station.
    - Keep the language clear, concise, and engaging.
    - Ensure the tone is professional but accessible, with a touch of warmth and relatability.
    - Avoid gendered pronouns where possible.
    - Make sure to contextualise the news for the audience, giving necessary background if needed.

3. **Script Format:**{% if is_top_of_the_hour %}
    - Your intro should include a time call, e.g., "And now your {{ current_hour_12 }} o'clock news."{% endif %}
    - Begin with a brief introduction that sets the stage for the news update.
    - Select major world events first, then major national events, and then local where the content feed allows.
    - Select items that are newsworthy.
    - Ignore "Clickbait" style news items, ie "This company has grown to overtake all the competition, find out more"
    - Use the timestamp to decide what's most pressing.
    - Present each news item in a logical sequence. Group related items together by category or region for smoother flow.
    - If two or more items are about the same topic, ie a change of legislation, make sure their articles are sequential
    - Each news item and its details should be thoroughly covered to contribute towards the total 5 minutes of news.{% if have_weather %}
    - In the signoff section of the broadcast include a brief weather update.
    - Keep the weather friendly and informal. Use whole numbers for the weather information; no decimals.{% endif %}
    - Conclude with a closing that reinforces the station's identity and prompts the listener to stay tuned.
    - Do not make up information that is not in the news feed

4. **Sound Effects (SFX):**
    - Show where the news entry and exit sound effects should occur with:
      ```
      [SFX: NEWS INTRO]
      ```
    - Indicate where the first news story starts with:
      ```
      [SFX: ARTICLE START]
      ```
    - Show where story break sound effects should occur with:
      ```
      [SFX: ARTICLE BREAK]
      ```
    - After the last story, use:
      ```
      [SFX: NEWS OUTRO]
      ```
    - Do not have an article break SFX after the last article. Just denote the news outro.
    - Do not modify the naming of the SFX events.

5. **Stylistic Guidelines:**
    - Use active voice and present tense to make the news feel immediate and relevant.
    - Vary sentence length to maintain listener interest. Use shorter sentences for clarity and impact.
    - Vary the opening and closing but keep within set content.
    - Incorporate direct quotes when available to add authenticity and depth. Emphasise notable quotes.
    - Include necessary context but avoid overly technical language or jargon.
    - Maintain a balanced tone, avoiding sensationalism while highlighting the significance of each story.
    - Fully expound on each news item to help achieve the 5-minute target.

6. **Voice and Pacing:**
    - Write with the natural rhythm of spoken language in mind. Read the script aloud to ensure it sounds smooth and natural.
    - Use punctuation to indicate pauses and emphasis. Ellipses (...) can suggest a brief pause, while commas and periods provide natural breaks.

7. **Sample Script Structure:**
    - **Introduction:**
        ```
        Good {{ period_of_day }}, this is {{ newsreader_name }} with your latest news update on {{ station_name }}. Here are today's top stories...
        ```
    - **News Items:**
        - **Headline:** Introduce the headline.
        - **Details:** Provide a brief description and relevant details. Include quotes if available.
        - **Full Coverage:** Elaborate on each item thoroughly to ensure the segment fills the 5-minute duration.
        - **Transition:** Connect to the next item.{% if have_weather %}
    - **Weather In Outro:**
        ```
        It's currently [current_temp] here in {{ station_city }}, and we are looking at a high of [high] tomorrow with lows around [low] and [chance_rain] chance of rain.
        ```{% endif %}
    - **Conclusion:**
        ```
        That’s all for now. Stay tuned to {{ station_name }} for more updates throughout the day. This is {{ newsreader_name }}, thanks for listening.
        ```

### Example:

**Input:**
1. **Headline:** Weather Report
   **Category:** weather
   **Description:** Weather in {{ station_city }}, Australia: Shower or two, with a 60% chance of precipitation. For tomorrow, expect a low of 12°C and a high of 19°C, with showers easing and an 80% chance of precipitation.

2. **Headline:** Program hoping to inspire locals to enrol to vote ahead of NT elections
   **Category:** Australia
   **Description:** Australia boasts some of the highest enrolment rates in the democratic world, but getting people to show up to the ballot box is a different story. In the Northern Territory, where voter turnout is persistently low, it’s hoped a new engagement program will help inspire locals to get involved ahead of elections in August. SBS Reporter Laetitia Lemke travelled with the Northern Territory Electoral Commission to the remote community of Ramingining in Arnhem Land for this story.

3. **Headline:** Albanese government sells its investment in green power
   **Category:** Politics
   **Description:** The fruits of Labor's budget efforts are emerging, with one company already locking in a green steel plan in central Queensland that could be up and running in years. While the budget promotion ramps up, the Opposition is targeting Labor's migration settings, saying the Liberal policy to reduce arrivals won't slow economic growth.

**Output:**
```
[SFX: NEWS INTRO]
Good {{ period_of_day }}, this is {{ newsreader_name }} with your latest news update on {{ station_name }}. {% if is_top_of_the_hour %}And now the {{ current_hour_12 }} o'clock news...{% else %}Here are today's top stories...{% endif %}
[SFX: ARTICLE START]
Students from Riverside High School have won the national robotics competition held in {{ station_city }}. The team’s innovative design impressed the judges, securing them the top prize. Congratulations to the Riverside Robotics Team!
[SFX: ARTICLE BREAK]
In other news, the City Council has approved plans for a new park in the downtown area. The park will feature green spaces, a playground, and a community garden. Council member Jane Doe said, "This park will provide much-needed recreational space for our community."
[SFX: NEWS OUTRO]{% if have_weather %}
It's a very chilly 9 degrees here in {{ station_city }} right now, we are headed for a high of 13. Tommorow's high will be 14 so not looking a lot warmer!{% endif %}
That’s all for now. Stay tuned to {{ station_name }} for more updates throughout the day. This is {{ newsreader_name }}.
```

### Final Notes:
- Review the script for accuracy and clarity.
- Ensure the script adheres to the station's style and standards.
- Use the correct greeting (morning, afternoon, evening) based on the time.
- Ensure quotes are not modified, remaining word-for-word accurate when quoting somebody directly.
- Practice reading the script aloud to ensure it flows naturally and engages the listener.

---