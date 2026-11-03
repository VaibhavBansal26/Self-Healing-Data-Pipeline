import {render, screen} from '@testing-library/react';
import {describe, expect, it} from 'vitest';
import {DataTable} from '../DataTable';

describe('DataTable', () => {
  it('renders an empty state for empty rows', () => {
    render(<DataTable rows={[]} cols={['component','status']} emptyTitle="Nothing loaded"/>);
    expect(screen.getByText('Nothing loaded')).toBeInTheDocument();
  });

  it('renders rows and humanized headers', () => {
    render(<DataTable rows={[{component:'consumer', problem_type:'consumer_down'}]} cols={['component','problem_type']}/>);
    expect(screen.getByText('consumer')).toBeInTheDocument();
    expect(screen.getByText('problem type')).toBeInTheDocument();
  });
});
