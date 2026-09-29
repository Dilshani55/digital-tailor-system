import React, { useState, useEffect, useRef } from 'react';
import { Sparkles, Check, Info, RefreshCw, AlertCircle, ChevronLeft, ChevronRight } from 'lucide-react';
import { fabricAPI } from '../services/api';
import FabricDetailsModal from './FabricDetailsModal';

export default function FabricRecommendation({
  detectedFeatures,
  selectedFabricId,
  onSelectFabric,
  validationError
}) {
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [modalFabric, setModalFabric] = useState(null);
  const [failedImages, setFailedImages] = useState({});
  const scrollContainerRef = useRef(null);

  const fetchRecommendations = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fabricAPI.getRecommendations(detectedFeatures || {});
      if (res.data && res.data.recommendations) {
        setRecommendations(res.data.recommendations);
        // If user hasn't selected a fabric yet, select the top "Best Match" fabric by default
        if (!selectedFabricId && res.data.recommendations.length > 0) {
          const topMatch = res.data.recommendations[0];
          onSelectFabric(topMatch.id, topMatch.name, topMatch.stretch === 'Stretchable' ? 'knit' : 'woven');
        }
      }
    } catch (err) {
      setError('Unable to load fabric recommendations. Please check connection and retry.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRecommendations();
  }, [
    detectedFeatures?.garment_type,
    detectedFeatures?.neckline,
    detectedFeatures?.sleeves,
    detectedFeatures?.darts,
    detectedFeatures?.seams
  ]);

  const handleImageError = (id) => {
    setFailedImages((prev) => ({ ...prev, [id]: true }));
  };

  const scrollLeft = () => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollBy({ left: -270, behavior: 'smooth' });
    }
  };

  const scrollRight = () => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollBy({ left: 270, behavior: 'smooth' });
    }
  };

  const getStatusBadgeStyle = (status, isBest) => {
    if (isBest || status === 'Best Match') {
      return { background: '#2D5A43', color: '#FFFFFF', border: '1px solid #1E3A2B' };
    }
    switch (status) {
      case 'Highly Suitable':
        return { background: '#D97706', color: '#FFFFFF', border: '1px solid #B45309' };
      case 'Suitable':
        return { background: '#2563EB', color: '#FFFFFF', border: '1px solid #1D4ED8' };
      default:
        return { background: '#6B7280', color: '#FFFFFF', border: '1px solid #4B5563' };
    }
  };

  return (
    <div style={{ marginTop: '20px', marginBottom: '20px' }}>
      
      {/* Custom Sleek Scrollbar Styles */}
      <style>{`
        .fabric-scroll-container::-webkit-scrollbar {
          height: 6px;
        }
        .fabric-scroll-container::-webkit-scrollbar-track {
          background: #E2E8F0;
          border-radius: 4px;
        }
        .fabric-scroll-container::-webkit-scrollbar-thumb {
          background: #2D5A43;
          border-radius: 4px;
        }
        .fabric-scroll-container::-webkit-scrollbar-thumb:hover {
          background: #1E3A2B;
        }
      `}</style>

      {/* Header Section */}
      <div style={{ marginBottom: '14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <h3 style={{ margin: 0, fontSize: '15px', fontWeight: '700', color: 'var(--text-primary, #0F172A)' }}>
              Recommended Materials for Your Design
            </h3>
            <span style={{
              fontSize: '11px',
              fontWeight: '600',
              padding: '2px 8px',
              borderRadius: '12px',
              background: 'rgba(45, 90, 67, 0.1)',
              color: 'var(--text-accent, #2D5A43)',
              border: '1px solid rgba(45, 90, 67, 0.2)',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px'
            }}>
              <Sparkles size={12} /> Rule-based recommendation
            </span>
          </div>
          <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-secondary, #64748B)' }}>
            Select a material to learn about its appearance, comfort, and suitability for your garment ({recommendations.length} materials available).
          </p>
        </div>

        {/* Carousel Navigation Arrow Buttons & Spinner */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {loading && (
            <span style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '4px', marginRight: '8px' }}>
              <RefreshCw size={12} className="spin" /> Updating scores...
            </span>
          )}

          {recommendations.length > 0 && (
            <div style={{ display: 'flex', gap: '6px' }}>
              <button
                type="button"
                onClick={scrollLeft}
                aria-label="Scroll left"
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  border: '1px solid var(--border-strong, #CBD5E1)',
                  background: '#FFFFFF',
                  color: 'var(--text-primary, #0F172A)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
                }}
              >
                <ChevronLeft size={18} />
              </button>
              <button
                type="button"
                onClick={scrollRight}
                aria-label="Scroll right"
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  border: 'none',
                  background: 'var(--text-accent, #2D5A43)',
                  color: '#FFFFFF',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  boxShadow: '0 2px 4px rgba(0,0,0,0.15)'
                }}
              >
                <ChevronRight size={18} />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Validation Warning Alert */}
      {validationError && (
        <div style={{
          marginBottom: '14px',
          padding: '10px 14px',
          background: '#FEF2F2',
          border: '1px solid #FCA5A5',
          borderRadius: '8px',
          color: '#991B1B',
          fontSize: '12px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <AlertCircle size={16} />
          <strong>{validationError}</strong>
        </div>
      )}

      {/* Loading State */}
      {loading && recommendations.length === 0 ? (
        <div style={{
          padding: '36px',
          textAlign: 'center',
          background: 'var(--surface-1, #FFFFFF)',
          borderRadius: '12px',
          border: '1px solid var(--border, #E2E8F0)'
        }}>
          <div style={{ fontSize: '13px', color: 'var(--text-secondary, #64748B)' }}>
            Analyzing garment structure and ranking suitable fabrics...
          </div>
        </div>
      ) : error ? (
        /* Error State with Retry Button */
        <div style={{
          padding: '24px',
          textAlign: 'center',
          background: '#FEF2F2',
          border: '1px solid #FECACA',
          borderRadius: '12px',
          color: '#991B1B'
        }}>
          <div style={{ fontSize: '13px', fontWeight: '600', marginBottom: '8px' }}>{error}</div>
          <button
            onClick={fetchRecommendations}
            className="btn btn-outline"
            style={{ fontSize: '12px', padding: '6px 14px', background: '#FFFFFF', color: '#991B1B', borderColor: '#FCA5A5' }}
          >
            <RefreshCw size={14} style={{ marginRight: '4px' }} /> Retry Recommendation Engine
          </button>
        </div>
      ) : (
        /* Horizontal Scrollable Fabric Cards Carousel Container */
        <div
          ref={scrollContainerRef}
          className="fabric-scroll-container"
          style={{
            display: 'flex',
            gap: '16px',
            overflowX: 'auto',
            scrollBehavior: 'smooth',
            paddingBottom: '12px',
            paddingTop: '4px',
            WebkitOverflowScrolling: 'touch'
          }}
        >
          {recommendations.map((fabric, idx) => {
            const isSelected = selectedFabricId === fabric.id;
            const isBestMatch = idx === 0 || fabric.recommendation_status === 'Best Match';

            return (
              <div
                key={fabric.id}
                onClick={() => onSelectFabric(fabric.id, fabric.name, fabric.stretch === 'Stretchable' ? 'knit' : 'woven')}
                style={{
                  position: 'relative',
                  border: isSelected ? '2px solid #16A34A' : '1px solid var(--border, #CBD5E1)',
                  borderRadius: '12px',
                  overflow: 'hidden',
                  background: isSelected ? '#F0FDF4' : 'var(--surface-1, #FFFFFF)',
                  boxShadow: isSelected ? '0 4px 12px rgba(22, 163, 74, 0.15)' : '0 1px 3px rgba(0, 0, 0, 0.05)',
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  transition: 'all 0.2s ease-in-out',
                  flex: '0 0 245px',
                  minWidth: '245px'
                }}
              >
                {/* Selected Checkmark Badge */}
                {isSelected && (
                  <div style={{
                    position: 'absolute',
                    top: '8px',
                    right: '8px',
                    background: '#16A34A',
                    color: '#FFFFFF',
                    borderRadius: '50%',
                    width: '24px',
                    height: '24px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    zIndex: 2,
                    boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
                  }}>
                    <Check size={16} />
                  </div>
                )}

                {/* Fabric Image & Status Badge */}
                <div style={{ height: '120px', width: '100%', position: 'relative', background: '#F1F5F9' }}>
                  {!failedImages[fabric.id] && fabric.local_image ? (
                    <img
                      src={fabric.local_image}
                      alt={`Close-up fabric texture image of ${fabric.name}`}
                      onError={() => handleImageError(fabric.id)}
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    />
                  ) : (
                    /* Fallback UI */
                    <div style={{
                      width: '100%',
                      height: '100%',
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      justifyContent: 'center',
                      background: 'linear-gradient(135deg, #2D5A43 0%, #1E3A2B 100%)',
                      color: '#FFFFFF',
                      padding: '8px'
                    }}>
                      <span style={{ fontSize: '20px', fontWeight: 'bold' }}>{fabric.name.charAt(0)}</span>
                      <span style={{ fontSize: '11px' }}>{fabric.name}</span>
                    </div>
                  )}

                  {/* Recommendation Badge overlay */}
                  <span style={{
                    position: 'absolute',
                    bottom: '8px',
                    left: '8px',
                    fontSize: '10px',
                    fontWeight: '700',
                    padding: '3px 8px',
                    borderRadius: '10px',
                    boxShadow: '0 2px 4px rgba(0,0,0,0.15)',
                    ...getStatusBadgeStyle(fabric.recommendation_status, isBestMatch)
                  }}>
                    {isBestMatch ? '★ Best Match' : fabric.recommendation_status}
                  </span>
                </div>

                {/* Card Content */}
                <div style={{ padding: '12px 14px', flex: 1, display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                    <strong style={{ fontSize: '14px', color: 'var(--text-primary, #0F172A)' }}>{fabric.name}</strong>
                    {isSelected && (
                      <span style={{ fontSize: '10px', color: '#16A34A', fontWeight: '700' }}>Selected</span>
                    )}
                  </div>

                  <p style={{
                    margin: 0,
                    fontSize: '11px',
                    color: 'var(--text-secondary, #64748B)',
                    lineHeight: '1.35',
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical',
                    overflow: 'hidden',
                    height: '28px'
                  }}>
                    {fabric.simple_description}
                  </p>

                  <div style={{ display: 'flex', gap: '6px', fontSize: '10px', flexWrap: 'wrap', marginTop: '2px' }}>
                    <span style={{ background: 'var(--surface-2, #F1F5F9)', padding: '2px 6px', borderRadius: '4px', color: 'var(--text-primary, #334155)' }}>
                      Weight: <strong>{fabric.weight}</strong>
                    </span>
                    <span style={{ background: 'var(--surface-2, #F1F5F9)', padding: '2px 6px', borderRadius: '4px', color: 'var(--text-primary, #334155)' }}>
                      Stretch: <strong>{fabric.stretch}</strong>
                    </span>
                  </div>

                  {/* 2 Main Advantages */}
                  <div style={{ marginTop: '4px', fontSize: '11px', color: 'var(--text-secondary, #475569)' }}>
                    {fabric.advantages?.slice(0, 2).map((adv, idx) => (
                      <div key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: '4px', marginBottom: '2px' }}>
                        <span style={{ color: '#16A34A', fontWeight: 'bold' }}>✓</span>
                        <span style={{ flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{adv}</span>
                      </div>
                    ))}
                  </div>

                  {/* Action Buttons Row */}
                  <div style={{ display: 'flex', gap: '8px', marginTop: 'auto', paddingTop: '10px' }}>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setModalFabric(fabric);
                      }}
                      style={{
                        flex: 1,
                        padding: '6px 10px',
                        fontSize: '11px',
                        fontWeight: '600',
                        borderRadius: '6px',
                        border: '1px solid var(--border-strong, #CBD5E1)',
                        background: '#FFFFFF',
                        color: 'var(--text-primary, #0F172A)',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '4px'
                      }}
                    >
                      <Info size={12} /> View Details
                    </button>

                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectFabric(fabric.id, fabric.name, fabric.stretch === 'Stretchable' ? 'knit' : 'woven');
                      }}
                      style={{
                        flex: 1,
                        padding: '6px 10px',
                        fontSize: '11px',
                        fontWeight: '600',
                        borderRadius: '6px',
                        border: 'none',
                        background: isSelected ? '#16A34A' : 'var(--text-accent, #2D5A43)',
                        color: '#FFFFFF',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '4px'
                      }}
                    >
                      {isSelected ? <Check size={12} /> : null}
                      {isSelected ? 'Selected' : 'Select Material'}
                    </button>
                  </div>

                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Details Modal */}
      {modalFabric && (
        <FabricDetailsModal
          fabric={modalFabric}
          isSelected={selectedFabricId === modalFabric.id}
          onSelect={(id) => {
            const found = recommendations.find((r) => r.id === id);
            if (found) {
              onSelectFabric(found.id, found.name, found.stretch === 'Stretchable' ? 'knit' : 'woven');
            }
          }}
          onClose={() => setModalFabric(null)}
        />
      )}

    </div>
  );
}
