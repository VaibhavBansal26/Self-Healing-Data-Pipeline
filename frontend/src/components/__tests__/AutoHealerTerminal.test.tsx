import {render, screen} from '@testing-library/react';
import {describe, expect, it} from 'vitest';
import {AutoHealerTerminal} from '../AutoHealerTerminal';

describe('AutoHealerTerminal', () => {
  it('shows sleeping state clearly', () => {
    render(<AutoHealerTerminal autoHealer={{state:'sleeping', recent_activity:[]}} traces={[]}/>);
    expect(screen.getByText(/Background Auto-Healer Console/i)).toBeInTheDocument();
    expect(screen.getByText(/Sleeping/i)).toBeInTheDocument();
  });

  it('shows healing state and terminal line', () => {
    const autoHealer = {
      state: 'healing',
      current_cycle_events: [{stage:'detect', status:'unhealthy_detected', metadata:{message:'Consumer is down'}, created_at:new Date().toISOString()}]
    };
    render(<AutoHealerTerminal autoHealer={autoHealer} traces={[]}/>);
    expect(screen.getByText(/Healing in progress/i)).toBeInTheDocument();
    expect(screen.getByText(/Consumer is down/i)).toBeInTheDocument();
  });
});
