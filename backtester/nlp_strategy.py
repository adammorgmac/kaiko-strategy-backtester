"""
Natural language strategy parser using Claude API.
"""
import os
import json
from typing import Dict, List, Optional
import anthropic
from dotenv import load_dotenv

from .strategies import TradeSignal, SignalType
from .advanced_strategies import get_advanced_strategy


class NLPStrategyParser:
    """Parse natural language strategy descriptions into executable strategies."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize with Anthropic API key."""
        if api_key is None:
            load_dotenv()
            api_key = os.getenv('ANTHROPIC_API_KEY')
        
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found. Set it in .env file.")
        
        self.client = anthropic.Anthropic(api_key=api_key)
    
    def parse_strategy(self, description: str) -> Dict:
        """
        Parse natural language strategy description into structured parameters.
        
        Args:
            description: Natural language strategy description
            
        Returns:
            Dictionary with strategy type and parameters
        """
        
        prompt = f"""You are an options trading strategy parser. Given a natural language description of an options trading strategy, extract the strategy type and parameters in JSON format.

Available strategy types:
- "simple_vol": Trade based on IV percentile (high_iv_threshold, low_iv_threshold)
- "skew": Trade put/call skew differences (skew_threshold, atm_range)
- "gamma_scalp": Target high gamma for scalping (min_gamma, target_dte)
- "calendar": Trade term structure (min_iv_diff, near_dte, far_dte)
- "straddle_screen": Screen for optimal straddles (max_iv, min_gamma, min_oi)

User description:
"{description}"

Extract:
1. Strategy type (one of the above)
2. Parameters (as key-value pairs)
3. Asset (btc, eth, or null for any)
4. Rationale (why this strategy makes sense)

Return ONLY valid JSON with this structure:
{{
  "strategy_type": "string",
  "parameters": {{}},
  "asset": "string or null",
  "rationale": "string"
}}

Examples:

Input: "Sell straddles when IV is above 80%"
Output: {{"strategy_type": "simple_vol", "parameters": {{"high_iv_threshold": 80, "low_iv_threshold": 20}}, "asset": null, "rationale": "Selling high IV to capture premium decay"}}

Input: "Buy BTC straddles with gamma above 0.001 for scalping"
Output: {{"strategy_type": "gamma_scalp", "parameters": {{"min_gamma": 0.001}}, "asset": "btc", "rationale": "High gamma allows profitable delta hedging"}}

Now parse the user's description above."""

        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        response_text = message.content[0].text
        
        # Extract JSON from response
        try:
            # Find JSON in response (might have markdown code blocks)
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = response_text.strip()
            
            parsed = json.loads(json_str)
            return parsed
            
        except json.JSONDecodeError as e:
            print(f"Error parsing Claude response: {e}")
            print(f"Response was: {response_text}")
            return None
    
    def create_strategy_from_nl(self, description: str):
        """
        Create an executable strategy from natural language description.
        
        Args:
            description: Natural language strategy description
            
        Returns:
            Strategy instance or None if parsing failed
        """
        parsed = self.parse_strategy(description)
        
        if not parsed:
            return None
        
        strategy_type = parsed.get('strategy_type')
        parameters = parsed.get('parameters', {})
        
        print(f"\n{'='*70}")
        print("PARSED STRATEGY")
        print(f"{'='*70}")
        print(f"Type: {strategy_type}")
        print(f"Parameters: {parameters}")
        print(f"Asset: {parsed.get('asset', 'any')}")
        print(f"Rationale: {parsed.get('rationale')}")
        print(f"{'='*70}\n")
        
        # Create strategy
        try:
            # Try advanced strategies first
            from .advanced_strategies import get_advanced_strategy
            strategy = get_advanced_strategy(strategy_type, parameters)
            return strategy
        except:
            # Fall back to basic strategies
            from .strategies import get_strategy
            try:
                strategy = get_strategy(strategy_type, parameters)
                return strategy
            except Exception as e:
                print(f"Error creating strategy: {e}")
                return None


class ConversationalBacktester:
    """
    Conversational interface for backtesting.
    Ask questions and get insights about strategies.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize with Anthropic API key."""
        if api_key is None:
            load_dotenv()
            api_key = os.getenv('ANTHROPIC_API_KEY')
        
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found")
        
        self.client = anthropic.Anthropic(api_key=api_key)
        self.conversation_history = []
    
    def ask(self, question: str, context: Dict = None) -> str:
        """
        Ask a question about options trading strategies.
        
        Args:
            question: User question
            context: Optional context (market data, signals, etc.)
            
        Returns:
            AI response
        """
        
        # Build context string
        context_str = ""
        if context:
            if 'market_data' in context:
                data = context['market_data']
                context_str += f"\nMarket Data Summary:\n"
                context_str += f"- Instruments: {len(data)}\n"
                context_str += f"- Avg IV: {data['mark_iv'].mean():.1f}%\n"
                context_str += f"- IV Range: {data['mark_iv'].min():.1f}% - {data['mark_iv'].max():.1f}%\n"
            
            if 'signals' in context:
                signals = context['signals']
                context_str += f"\nGenerated Signals: {len(signals)}\n"
            
            if 'spot_price' in context:
                context_str += f"\nCurrent Spot: ${context['spot_price']:,.2f}\n"
        
        system_prompt = """You are an expert options trader and quantitative analyst specializing in cryptocurrency derivatives. 

You help users:
- Understand options trading strategies
- Interpret market data and Greeks
- Optimize strategy parameters
- Explain risk/reward tradeoffs
- Suggest improvements to strategies

Be concise, practical, and use specific numbers when available. If asked about current market conditions, use the provided context data."""

        user_message = question
        if context_str:
            user_message = f"{context_str}\n\nUser Question: {question}"
        
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })
        
        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=system_prompt,
            messages=self.conversation_history
        )
        
        response = message.content[0].text
        
        self.conversation_history.append({
            "role": "assistant",
            "content": response
        })
        
        return response


# CLI tool for testing
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m backtester.nlp_strategy 'your strategy description'")
        print("\nExamples:")
        print('  "Sell straddles when IV is above 75%"')
        print('  "Buy high gamma options for scalping"')
        print('  "Trade calendar spreads when near-term IV is 10% higher than far"')
        sys.exit(1)
    
    description = sys.argv[1]
    
    print(f"\nParsing: {description}\n")
    
    parser = NLPStrategyParser()
    result = parser.parse_strategy(description)
    
    if result:
        print("\n✅ Successfully parsed!")
        print(json.dumps(result, indent=2))
        
        # Try to create strategy
        strategy = parser.create_strategy_from_nl(description)
        
        if strategy:
            print(f"\n✅ Created strategy: {strategy.name}")
    else:
        print("\n❌ Failed to parse strategy")