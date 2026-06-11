import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ReactFlowProvider } from '@xyflow/react';
import OuterFrame from '../OuterFrame.jsx';

function wrap(ui) {
  return render(<ReactFlowProvider>{ui}</ReactFlowProvider>);
}

describe('OuterFrame', () => {
  it('renders the frame label', () => {
    wrap(<OuterFrame data={{ label: 'Books' }} />);
    expect(screen.getByText('Books')).toBeInTheDocument();
  });

  it('falls back to "Untitled Frame" when label is empty', () => {
    wrap(<OuterFrame data={{ label: '' }} />);
    expect(screen.getByText(/Untitled Frame/i)).toBeInTheDocument();
  });

  it('marks the auto Loose Ideas frame visually', () => {
    const { container } = wrap(
      <OuterFrame data={{ label: 'Loose ideas', isAutoLooseIdeas: true }} />,
    );
    expect(container.querySelector('.oc-frame.is-loose')).not.toBeNull();
  });

  it('does NOT add is-loose class on a normal frame', () => {
    const { container } = wrap(
      <OuterFrame data={{ label: 'Normal', isAutoLooseIdeas: false }} />,
    );
    expect(container.querySelector('.oc-frame.is-loose')).toBeNull();
    expect(container.querySelector('.oc-frame')).not.toBeNull();
  });
});
